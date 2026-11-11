"""The whole path with the real sandbox: tasks run in separate processes, memory is written and read, results are saved and reported."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from lucifer.backends.ollama import OllamaBackend
from lucifer.backends.sim import SimBackend
from lucifer.cli import main
from lucifer.experiment import Config, run_experiment
from lucifer.report import load, render
from lucifer.sandbox import SandboxExecutor
from lucifer.stats import paired_bootstrap
from lucifer.tasks import TASKS


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("run")
    run_experiment(Config(SimBackend("learner"), SandboxExecutor(), seeds=(0, 1), run_id="t", out_dir=out))
    return out


def test_counts_and_files(run_dir):
    rows, audits, meta = load(run_dir)
    assert len(rows) == 2 * 3 * 36  # seeds x conditions x (12 experience + 24 evaluation tasks)
    assert {r["phase"] for r in rows} == {"experience", "similar", "transfer", "replay"}
    assert len(audits) == 2 * 2 and all(a["ok"] for a in audits)
    assert (run_dir / "attempts.jsonl").read_text().count("\n") >= len(rows)
    assert meta["backend"] == "sim-learner"


def test_baseline_never_reads_or_writes_memory(run_dir):
    rows, _, _ = load(run_dir)
    assert all(r["lessons_shown"] == [] and r["memory_version"] == 0 for r in rows if r["condition"] == "baseline")


def test_memory_is_frozen_during_evaluation(run_dir):
    rows, _, _ = load(run_dir)
    for seed in (0, 1):
        for cond in ("lucifer", "irrelevant"):
            versions = {r["memory_version"] for r in rows if r["seed"] == seed and r["condition"] == cond and r["phase"] != "experience"}
            assert len(versions) == 1, "evaluation must not write lessons"


def test_every_condition_sees_the_same_tasks_in_the_same_order(run_dir):
    rows, _, _ = load(run_dir)
    order = lambda c: [r["task_id"] for r in rows if r["seed"] == 0 and r["condition"] == c]
    assert order("baseline") == order("lucifer") == order("irrelevant")


def test_report_renders(run_dir):
    text = render(*load(run_dir))
    assert "Gate 1" in text and "baseline" in text and "irrelevant" in text


def test_same_inputs_give_the_same_results():
    def flags():
        out = run_experiment(Config(SimBackend("learner"), SandboxExecutor(), seeds=(3,)))
        return [(r["condition"], r["task_id"], r["pass_at_1"], r["pass_at_2"], tuple(r["lessons_shown"])) for r in out.rows]
    assert flags() == flags()


def test_bootstrap_basics():
    same = {"a": 0.5, "b": 0.5, "c": 0.5}
    assert paired_bootstrap(same, same)[1:] == (0.0, 0.0)
    shifted = paired_bootstrap({t: 0.2 for t in "abcdefgh"}, {t: 0.7 for t in "abcdefgh"})
    assert shifted[0] == pytest.approx(0.5) and shifted[1] > 0.4
    assert paired_bootstrap({}, {}) == (0.0, 0.0, 0.0)


def test_cli_runs_and_reports(tmp_path, capsys):
    assert main(["run", "--backend", "sim-null", "--seeds", "1", "--out", str(tmp_path / "x")]) == 0
    assert "All three gates" in capsys.readouterr().out
    assert main(["report", str(tmp_path / "x")]) == 0


class _FakeOllama(BaseHTTPRequestHandler):
    """Answers like a model that is right on the first try: it looks the function name up in the prompt and returns the reference."""
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        prompt = body["messages"][0]["content"]
        task = next(t for t in TASKS if f"`{t.entry}`" in prompt.split("Write a Python function", 1)[-1][:80])
        reply = {"message": {"content": f"<think>hmm</think>```python\n{task.reference}\n```"}, "prompt_eval_count": 11, "eval_count": 7}
        data = json.dumps(reply).encode()
        self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_ollama_backend_over_http_end_to_end():
    server = HTTPServer(("127.0.0.1", 0), _FakeOllama)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        backend = OllamaBackend("fake:1b", f"http://127.0.0.1:{server.server_port}")
        gen = backend.generate("Write a Python function `mean`.", seed=1)
        assert "<think>" not in gen.text and gen.prompt_tokens == 11 and gen.completion_tokens == 7
        out = run_experiment(Config(backend, SandboxExecutor(), seeds=(0,), conditions=("baseline",)))
        assert len(out.rows) == 36 and all(r["pass_at_1"] for r in out.rows)
        assert all(r["prompt_tokens"] == 11 for r in out.rows)
    finally:
        server.shutdown()
