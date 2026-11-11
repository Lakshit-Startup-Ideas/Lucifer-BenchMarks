from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .experiment import Config, run_experiment
from .tasks import TASK_SETS, task_set
from .report import load, render
from .sandbox import FastExecutor, SandboxExecutor


def _make_backend(a, parser):
    if a.backend == "ollama":
        from .backends.ollama import OllamaBackend
        return OllamaBackend(a.model, a.host, temperature=a.temperature)
    if a.backend == "groq":
        from .backends.groq import GroqBackend
        try:
            return GroqBackend(a.model, temperature=a.temperature, min_interval_s=a.min_interval, reasoning_effort=a.reasoning_effort)
        except RuntimeError as e:
            parser.error(str(e))
    parser.error(f"unknown backend {a.backend}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lucifer", description="Does an agent get better at later tasks by learning from its own experience?")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the experiment")
    run.add_argument("--backend", default="sim-learner", help="sim-null | sim-learner | sim-harmful | ollama | groq")
    run.add_argument("--model", help="Ollama model tag (for --backend ollama)")
    run.add_argument("--host", default="http://127.0.0.1:11434")
    run.add_argument("--seeds", type=int, default=5)
    run.add_argument("--k", type=int, default=3, help="lessons shown per task")
    run.add_argument("--taskset", choices=TASK_SETS, default="all", help="pitfall (fully specified tasks), convention (hidden conventions) or all")
    run.add_argument("--out", type=Path, help="results folder (default results/<run id>)")
    run.add_argument("--run-id", default=None)
    run.add_argument("--min-interval", type=float, default=2.2, help="seconds between Groq calls (free-tier rate limit)")
    run.add_argument("--reasoning-effort", choices=["low", "medium", "high"], help="for Groq reasoning models such as gpt-oss")
    run.add_argument("--temperature", type=float, default=0.3, help="sampling temperature (higher gives more variety between seeds)")
    cal = sub.add_parser("calibrate", help="run the baseline only and show which tasks are too easy or too hard")
    cal.add_argument("--backend", default="groq", help="ollama | groq")
    cal.add_argument("--model", required=True)
    cal.add_argument("--host", default="http://127.0.0.1:11434")
    cal.add_argument("--seeds", type=int, default=3)
    cal.add_argument("--min-interval", type=float, default=2.2)
    cal.add_argument("--reasoning-effort", choices=["low", "medium", "high"])
    cal.add_argument("--temperature", type=float, default=0.3)
    cal.add_argument("--taskset", choices=TASK_SETS, default="all")
    cal.add_argument("--out", type=Path)
    dash = sub.add_parser("dashboard", help="open the web dashboard over the saved runs")
    dash.add_argument("--results", type=Path, default=Path("results"))
    dash.add_argument("--port", type=int, default=8765)
    dash.add_argument("--no-open", action="store_true")
    rep = sub.add_parser("report", help="print the results table and the three gates")
    rep.add_argument("folder", type=Path)
    a = p.parse_args(argv)

    if a.cmd == "dashboard":
        from .server import serve
        serve(a.results, a.port, open_browser=not a.no_open)
        return 0

    if a.cmd == "report":
        print(render(*load(a.folder)))
        return 0

    if a.cmd == "calibrate":
        from .calibrate import calibrate, render_calibration
        backend = _make_backend(a, p)
        out = a.out or Path("results") / f"calibrate-{a.backend}-{a.model}".replace(":", "_").replace("/", "_")
        per_task = calibrate(backend, SandboxExecutor(), tuple(range(a.seeds)), out, progress=lambda s: print(f"seed {s} done", file=sys.stderr), tasks=task_set(a.taskset))
        print(render_calibration(per_task, backend.name))
        return 0

    if a.backend.startswith("sim-"):
        from .backends.sim import SimBackend
        backend, executor = SimBackend(a.backend.removeprefix("sim-")), SandboxExecutor()
        print("NOTE: simulated agent. This checks the measuring machinery; it says nothing about real models.", file=sys.stderr)
    elif a.backend in ("ollama", "groq"):
        if not a.model:
            p.error(f"--backend {a.backend} needs --model")
        backend, executor = _make_backend(a, p), SandboxExecutor()
    else:
        p.error(f"unknown backend {a.backend}")
    run_id = a.run_id or f"{a.backend}-{a.model or 'sim'}".replace(":", "_").replace("/", "_")
    out = a.out or Path("results") / run_id
    cfg = Config(backend, executor, seeds=tuple(range(a.seeds)), k=a.k, run_id=run_id, out_dir=out, tasks=task_set(a.taskset))
    run_experiment(cfg, progress=lambda s, c: print(f"seed {s} · {c} done", file=sys.stderr))
    print(render(*load(out)))
    print(f"\nSaved to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
