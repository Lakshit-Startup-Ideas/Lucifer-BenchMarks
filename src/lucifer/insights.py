"""Everything the dashboard shows is computed here from the files a run saved (rows, spans, memories). No number is typed in by hand."""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import fmean

from .gates import evaluate
from .stats import task_means
from .tasks import BY_ID

CONDITIONS = ("baseline", "lucifer", "irrelevant")
OPERATIONS = ("retrieve_memory", "build_prompt", "llm.generate", "sandbox.run_tests", "memory.write")
EVAL_PHASES = ("similar", "transfer", "replay")


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    return v[min(len(v) - 1, int(p / 100 * len(v)))]


@dataclass
class Run:
    id: str
    folder: Path
    meta: dict
    rows: list[dict]
    audits: list[dict]
    spans: list[dict]
    memories: list[dict]
    _by_trace: dict[str, list[dict]] = field(default_factory=dict)

    def trace(self, trace_id: str) -> list[dict]:
        if not self._by_trace:
            for s in self.spans:
                self._by_trace.setdefault(s["trace_id"], []).append(s)
        return self._by_trace.get(trace_id, [])


def load_run(folder: Path) -> Run:
    def read(name, default):
        f = folder / name
        return json.loads(f.read_text()) if f.exists() else default

    spans = []
    f = folder / "spans.jsonl"
    if f.exists():
        spans = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    return Run(folder.name, folder, read("meta.json", {}), read("rows.json", []), read("audits.json", []), spans, read("memories.json", []))


def list_runs(root: Path) -> list[dict]:
    out = []
    for d in sorted(root.iterdir() if root.exists() else [], key=lambda p: p.stat().st_mtime, reverse=True):
        if (d / "rows.json").exists():
            meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
            n = len(json.loads((d / "rows.json").read_text()))
            out.append({"id": d.name, "backend": meta.get("backend", "?"), "seeds": len(meta.get("seeds", [])), "solves": n,
                        "has_traces": (d / "spans.jsonl").exists(), "modified": d.stat().st_mtime})
    return out


def summary(run: Run) -> dict:
    rows, spans = run.rows, run.spans
    conds = [c for c in CONDITIONS if any(r["condition"] == c for r in rows)]
    primary = ("similar", "transfer")

    def rate(cond: str, phases) -> float:
        m = task_means(rows, cond, tuple(phases))
        return fmean(m.values()) if m else 0.0

    kpis = {}
    for c in conds:
        sel = [r for r in rows if r["condition"] == c]
        kpis[c] = {"pass_primary": rate(c, primary), "pass_replay": rate(c, ("replay",)), "solves": len(sel),
                   "avg_solve_ms": fmean(r["wall_ms"] for r in sel) if sel else 0, "avg_tokens": fmean(r["prompt_tokens"] + r["completion_tokens"] for r in sel) if sel else 0,
                   "avg_attempts": fmean(r["attempts"] for r in sel) if sel else 0}

    phase_bars = [{"phase": ph, **{c: rate(c, (ph,)) for c in conds}} for ph in ("experience", "similar", "transfer", "replay")]
    families = sorted({r["family"] for r in rows}, key=lambda f: (f == "mixed", f))
    radar = {"axes": families, **{c: [fmean(task_means(rows, c, EVAL_PHASES).get(t, 0) for t in {r["task_id"] for r in rows if r["family"] == f}) for f in families] for c in conds}}

    # learning curve: running average of first-try success by position in the experience phase (smoother than raw per-position rates)
    curve = {}
    for c in conds:
        pos: dict[int, list[float]] = defaultdict(list)
        counter: dict[int, int] = defaultdict(int)
        for r in rows:
            if r["condition"] == c and r["phase"] == "experience":
                counter[r["seed"]] += 1
                pos[counter[r["seed"]]].append(1.0 if r["pass_at_1"] else 0.0)
        running, seen = [], []
        for p, v in sorted(pos.items()):
            seen.extend(v)
            running.append({"position": p, "pass": fmean(seen), "raw": fmean(v)})
        curve[c] = running

    outcomes = {}
    for c in conds:
        sel = [r for r in rows if r["condition"] == c]
        outcomes[c] = {"first_try": sum(r["pass_at_1"] for r in sel), "fixed_on_retry": sum(r["pass_at_2"] and not r["pass_at_1"] for r in sel), "failed": sum(not r["pass_at_2"] for r in sel)}

    ops = []
    stack: dict[str, dict[str, list[float]]] = {c: defaultdict(list) for c in conds}
    cond_of_trace = {r["trace_id"]: r["condition"] for r in rows if "trace_id" in r}
    by_op: dict[str, list[dict]] = defaultdict(list)
    for s in spans:
        by_op[s["name"] if s["kind"] != "attempt" and s["kind"] != "root" else s["kind"]].append(s)
        c = cond_of_trace.get(s["trace_id"])
        if c in stack and s["name"] in OPERATIONS:
            stack[c][s["name"]].append(s["duration_ms"])
    for name in list(OPERATIONS) + ["attempt", "root"]:
        ss = by_op.get(name, [])
        if ss:
            d = [s["duration_ms"] for s in ss]
            ops.append({"operation": "solve (whole task)" if name == "root" else ("attempt" if name == "attempt" else name), "count": len(ss), "mean_ms": fmean(d), "p50_ms": _percentile(d, 50),
                        "p95_ms": _percentile(d, 95), "max_ms": max(d), "total_ms": sum(d), "errors": sum(s["status"] == "error" for s in ss)})
    latency_stack = {c: {op: (fmean(stack[c][op]) if stack[c][op] else 0.0) for op in OPERATIONS} for c in conds}

    per_task: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        per_task[r["task_id"]].append(r)
    hardest = sorted(({"task_id": t, "family": v[0]["family"], "first_try_fail": 1 - fmean(1.0 if r["pass_at_1"] else 0.0 for r in v), "avg_attempts": fmean(r["attempts"] for r in v), "solves": len(v)} for t, v in per_task.items()),
                     key=lambda d: (-d["first_try_fail"], -d["avg_attempts"]))[:8]

    phases = ("experience", "similar", "transfer", "replay")
    tasks = {ph: len({r["task_id"] for r in rows if r["phase"] == ph}) for ph in phases}
    tasks["primary"] = len({r["task_id"] for r in rows if r["phase"] in primary})
    radar_n = {f: len({r["task_id"] for r in rows if r["family"] == f}) for f in families}

    # retrieval quality: of the lessons shown on evaluation tasks, how many came from the same task family?
    meta_of = {r["trace_id"]: (r["condition"], r["phase"], r["family"]) for r in rows if "trace_id" in r}
    shown_total: dict[str, int] = defaultdict(int)
    shown_match: dict[str, int] = defaultdict(int)
    solves: dict[str, int] = defaultdict(int)
    covered: dict[str, int] = defaultdict(int)
    for sp in spans:
        if sp["kind"] != "retrieval":
            continue
        cond, phase, family = meta_of.get(sp["trace_id"], (None, None, None))
        if cond not in ("lucifer", "irrelevant") or phase not in EVAL_PHASES or family == "mixed":
            continue
        got = sp["attrs"].get("lessons_shown", [])
        match = sum(1 for l in got if (BY_ID.get(str(l.get("task_id", "")).split("#")[0]) and BY_ID[str(l["task_id"]).split("#")[0]].family == family))
        solves[cond] += 1
        shown_total[cond] += len(got)
        shown_match[cond] += match
        covered[cond] += 1 if match else 0
    retrieval = {c: {"precision": (shown_match[c] / shown_total[c]) if shown_total[c] else None, "coverage": covered[c] / solves[c] if solves[c] else None,
                     "avg_shown": shown_total[c] / solves[c] if solves[c] else 0.0, "solves": solves[c]} for c in ("lucifer", "irrelevant") if solves[c]}

    gates = evaluate(rows, run.audits, resamples=3000) if {"baseline", "lucifer"} <= set(conds) else None
    simulated = any(s["attrs"].get("simulated") for s in spans if s["kind"] == "llm")
    return {"id": run.id, "meta": run.meta, "conditions": conds, "simulated": simulated or str(run.meta.get("backend", "")).startswith("sim-"), "kpis": kpis, "phase_bars": phase_bars,
            "radar": radar, "curve": curve, "outcomes": outcomes, "operations": ops, "latency_stack": latency_stack, "hardest": hardest, "gates": gates,
            "tasks": tasks, "radar_n": radar_n, "retrieval": retrieval,
            "totals": {"traces": len(rows), "spans": len(spans), "attempts": sum(r["attempts"] for r in rows), "seeds": len(run.meta.get("seeds", [])),
                       "lessons": sum(len(m["lessons"]) for m in run.memories)}}


def trace_list(run: Run, *, condition=None, seed=None, phase=None, task=None, failed=False, q="", limit=300, offset=0) -> dict:
    items = []
    for r in run.rows:
        if "trace_id" not in r:  # a run saved before tracing existed
            continue
        if condition and r["condition"] != condition:
            continue
        if seed is not None and r["seed"] != seed:
            continue
        if phase and r["phase"] != phase:
            continue
        if task and r["task_id"] != task:
            continue
        if failed and r["pass_at_1"]:
            continue
        if q and q.lower() not in (r["task_id"] + " " + r["family"] + " " + r["condition"]).lower():
            continue
        items.append({"trace_id": r["trace_id"], "task_id": r["task_id"], "family": r["family"], "condition": r["condition"], "seed": r["seed"], "phase": r["phase"],
                      "pass_at_1": r["pass_at_1"], "pass_at_2": r["pass_at_2"], "attempts": r["attempts"], "duration_ms": r["wall_ms"], "lessons_shown": len(r["lessons_shown"])})
    return {"total": len(items), "items": items[offset:offset + limit]}


def memory_view(run: Run, condition: str | None, seed: int | None) -> list[dict]:
    return [m for m in run.memories if (not condition or m["condition"] == condition) and (seed is None or m["seed"] == seed)]
