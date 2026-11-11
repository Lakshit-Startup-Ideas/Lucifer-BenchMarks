from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .experiment import Config, run_experiment
from .report import load, render
from .sandbox import FastExecutor, SandboxExecutor


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lucifer", description="Does an agent get better at later tasks by learning from its own experience?")
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run the experiment")
    run.add_argument("--backend", default="sim-learner", help="sim-null | sim-learner | sim-harmful | ollama")
    run.add_argument("--model", help="Ollama model tag (for --backend ollama)")
    run.add_argument("--host", default="http://127.0.0.1:11434")
    run.add_argument("--seeds", type=int, default=5)
    run.add_argument("--k", type=int, default=3, help="lessons shown per task")
    run.add_argument("--out", type=Path, help="results folder (default results/<run id>)")
    run.add_argument("--run-id", default=None)
    rep = sub.add_parser("report", help="print the results table and the three gates")
    rep.add_argument("folder", type=Path)
    a = p.parse_args(argv)

    if a.cmd == "report":
        print(render(*load(a.folder)))
        return 0

    if a.backend.startswith("sim-"):
        from .backends.sim import SimBackend
        backend, executor = SimBackend(a.backend.removeprefix("sim-")), SandboxExecutor()
        print("NOTE: simulated agent. This checks the measuring machinery; it says nothing about real models.", file=sys.stderr)
    elif a.backend == "ollama":
        if not a.model:
            p.error("--backend ollama needs --model, for example --model qwen3:8b")
        from .backends.ollama import OllamaBackend
        backend, executor = OllamaBackend(a.model, a.host), SandboxExecutor()
    else:
        p.error(f"unknown backend {a.backend}")
    run_id = a.run_id or f"{a.backend}-{a.model or 'sim'}".replace(":", "_").replace("/", "_")
    out = a.out or Path("results") / run_id
    cfg = Config(backend, executor, seeds=tuple(range(a.seeds)), k=a.k, run_id=run_id, out_dir=out)
    run_experiment(cfg, progress=lambda s, c: print(f"seed {s} · {c} done", file=sys.stderr))
    print(render(*load(out)))
    print(f"\nSaved to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
