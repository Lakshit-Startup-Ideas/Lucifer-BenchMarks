import json
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest

from lucifer.backends.sim import SimBackend
from lucifer.experiment import Config, run_experiment
from lucifer.insights import list_runs, load_run, summary
from lucifer.sandbox import FastExecutor
from lucifer.server import Store, make_handler
from lucifer.tasks import by_split
from lucifer.tracing import Tracer

EXPERIENCE = len(by_split('exp'))
SOLVES_PER_RUN = EXPERIENCE * 2 + len(by_split('sim')) + len(by_split('xfer'))
TRACES = 2 * 3 * SOLVES_PER_RUN  # two seeds, three conditions


# ---- tracing -------------------------------------------------------------------------------------------------------------------
def test_spans_nest_and_the_clock_adds_up():
    tr = Tracer("t1", "solve x", task_id="x")
    with tr.span("a", "retrieval"):
        pass
    with tr.span("attempt 1", "attempt"):
        with tr.span("llm.generate", "llm") as g:
            g.duration_ms = 100.0
        with tr.span("sandbox.run_tests", "execution") as e:
            e.duration_ms = 20.0
            e.status = "error"
    spans = tr.finish("error", pass_at_1=False)
    by = {s["name"]: s for s in spans}
    assert [s["name"] for s in spans] == ["solve x", "a", "attempt 1", "llm.generate", "sandbox.run_tests"]  # parents come before children
    assert by["llm.generate"]["parent_id"] == by["attempt 1"]["span_id"] and by["attempt 1"]["parent_id"] == by["solve x"]["span_id"]
    assert by["llm.generate"]["start_ms"] == pytest.approx(by["a"]["duration_ms"] + by["a"]["start_ms"], abs=1e-3)
    assert by["sandbox.run_tests"]["start_ms"] == pytest.approx(by["llm.generate"]["start_ms"] + 100.0, abs=1e-3)
    assert by["attempt 1"]["duration_ms"] == pytest.approx(120.0, abs=1e-3)  # a parent lasts as long as its steps
    assert by["solve x"]["duration_ms"] == pytest.approx(by["a"]["duration_ms"] + 120.0, abs=1e-3)
    assert by["solve x"]["status"] == "error" and by["solve x"]["attrs"]["pass_at_1"] is False


# ---- a small saved run to read back ---------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def results_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("results")
    run_experiment(Config(SimBackend("learner"), FastExecutor(), seeds=(0, 1), run_id="small", out_dir=root / "small"))
    (root / "old-format").mkdir()  # a run saved before tracing existed
    (root / "old-format" / "rows.json").write_text(json.dumps([{"condition": "baseline", "phase": "similar", "task_id": "t", "family": "empty", "seed": 0, "pass_at_1": True, "pass_at_2": True,
                                                                   "attempts": 1, "wall_ms": 1.0, "prompt_tokens": 1, "completion_tokens": 1, "lessons_shown": [], "memory_version": 0}]))
    return root


def test_every_solve_has_a_trace_with_the_expected_steps(results_root):
    run = load_run(results_root / "small")
    assert len(run.rows) == TRACES
    for row in run.rows[:50] + run.rows[-50:]:
        spans = run.trace(row["trace_id"])
        names = [s["name"] for s in spans]
        assert names[0] == f"solve {row['task_id']}" and names[1:3] == ["retrieve_memory", "build_prompt"]
        assert names.count("llm.generate") == row["attempts"] == names.count("sandbox.run_tests")
        assert (row["phase"] == "experience" and row["condition"] != "baseline") == ("memory.write" in names)
        assert spans[0]["status"] == ("ok" if row["pass_at_2"] else "error")
        ends = [s["start_ms"] + s["duration_ms"] for s in spans[1:]]
        assert max(ends) <= spans[0]["duration_ms"] + 0.01  # nothing runs past the end of the solve (times are rounded to 0.001 ms)


def test_summary_is_complete_and_consistent(results_root):
    s = summary(load_run(results_root / "small"))
    assert s["conditions"] == ["baseline", "lucifer", "irrelevant"] and s["simulated"] is True
    assert s["totals"]["traces"] == TRACES and s["totals"]["spans"] > TRACES * 5
    assert [p["phase"] for p in s["phase_bars"]] == ["experience", "similar", "transfer", "replay"]
    assert all(0 <= p[c] <= 1 for p in s["phase_bars"] for c in s["conditions"])
    for c, o in s["outcomes"].items():
        assert o["first_try"] + o["fixed_on_retry"] + o["failed"] == s["kpis"][c]["solves"]
    assert {o["operation"] for o in s["operations"]} >= {"retrieve_memory", "llm.generate", "sandbox.run_tests", "memory.write"}
    assert s["gates"]["gate3_auditability"]["passed"]
    assert len(s["curve"]["lucifer"]) == EXPERIENCE and s["curve"]["lucifer"][-1]["pass"] <= 1


# ---- the web API ---------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def base_url(results_root):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Store(results_root)))
    Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.headers.get("content-type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", ""), e.read()


def test_api_lists_runs_summary_traces_and_memory(base_url):
    status, _, body = get(f"{base_url}/api/runs")
    runs = {r["id"]: r for r in json.loads(body)}
    assert status == 200 and runs["small"]["has_traces"] and not runs["old-format"]["has_traces"]
    assert json.loads(get(f"{base_url}/api/runs/small/summary")[2])["totals"]["traces"] == TRACES

    listing = json.loads(get(f"{base_url}/api/runs/small/traces?condition=lucifer&phase=similar&seed=1&limit=5")[2])
    assert listing["total"] == len(by_split("sim")) and len(listing["items"]) == 5 and all(i["condition"] == "lucifer" and i["seed"] == 1 for i in listing["items"])
    failed = json.loads(get(f"{base_url}/api/runs/small/traces?failed=1&limit=1000")[2])
    assert failed["items"] and all(not i["pass_at_1"] for i in failed["items"])

    tid = listing["items"][0]["trace_id"]  # contains slashes
    detail = json.loads(get(f"{base_url}/api/runs/small/traces/{tid}")[2])
    assert detail["trace_id"] == tid and detail["spans"][0]["kind"] == "root"
    assert get(f"{base_url}/api/runs/small/traces/nope/nope")[0] == 404

    memory = json.loads(get(f"{base_url}/api/runs/small/memory?condition=lucifer&seed=0")[2])
    assert len(memory) == 1 and memory[0]["lessons"] and {"hash", "version", "text"} <= set(memory[0]["lessons"][0])


def test_old_runs_do_not_crash_the_api(base_url):
    assert json.loads(get(f"{base_url}/api/runs/old-format/traces")[2])["total"] == 0
    assert json.loads(get(f"{base_url}/api/runs/old-format/summary")[2])["totals"]["spans"] == 0


def test_static_files_are_served_and_nothing_outside_the_web_folder_is(base_url):
    status, ctype, body = get(f"{base_url}/")
    assert status == 200 and "text/html" in ctype and b"Lucifer Lab" in body
    assert get(f"{base_url}/app.js")[0] == 200 and "javascript" in get(f"{base_url}/app.js")[1]
    for bad in ("/../server.py", "/..%2fserver.py", "/%2e%2e/%2e%2e/pyproject.toml", "/api/runs/..%2f..%2fetc/summary", "/api/runs/../summary", "/api/runs/%2e%2e/traces"):
        status, _, body = get(base_url + bad)
        assert status in (404, 400) or b"[project]" not in body, bad
        assert b"class SimBackend" not in body and b"[project]" not in body and b"root:" not in body
    assert get(f"{base_url}/api/runs/does-not-exist/summary")[0] == 404
