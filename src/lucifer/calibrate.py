"""Difficulty calibration: run the baseline alone and see which tasks leave room to show learning (the plan keeps tasks with 20-80% pass@1)."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean

from .backends.base import Backend
from .experiment import Config, run_experiment
from .sandbox import Executor
from .tasks import BY_ID, FAMILIES

LOW, HIGH = 0.2, 0.8


def calibrate(backend: Backend, executor: Executor, seeds: tuple[int, ...], out_dir: Path | None = None, progress=None, tasks=None) -> dict[str, float]:
    result = run_experiment(Config(backend, executor, seeds=seeds, conditions=("baseline",), run_id="calibrate", tasks=tasks), progress=lambda s, c: progress(s) if progress else None)
    by_task: dict[str, list[float]] = defaultdict(list)
    for r in result.rows:
        by_task[r["task_id"]].append(1.0 if r["pass_at_1"] else 0.0)
    per_task = {t: fmean(v) for t, v in by_task.items()}
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "per_task.json").write_text(json.dumps({"backend": backend.name, "seeds": list(seeds), "pass_at_1": per_task}, indent=1))
        (out_dir / "attempts.jsonl").write_text("\n".join(json.dumps(a) for a in result.attempts) + "\n")
    return per_task


def render_calibration(per_task: dict[str, float], backend_name: str) -> str:
    usable = [t for t, v in per_task.items() if LOW <= v <= HIGH]
    easy = [t for t, v in per_task.items() if v > HIGH]
    hard = [t for t, v in per_task.items() if v < LOW]
    mean = fmean(per_task.values()) if per_task else 0.0
    lines = [f"Baseline calibration · {backend_name} · {len(per_task)} tasks", "", f"mean pass@1 {mean:.0%}",
             f"usable (between {LOW:.0%} and {HIGH:.0%}): {len(usable)}   too easy (above {HIGH:.0%}): {len(easy)}   too hard (below {LOW:.0%}): {len(hard)}", ""]
    for family in (*FAMILIES, "mixed"):
        ids = [t for t in per_task if BY_ID[t].family == family]
        if ids:
            lines.append(f"{family:<9}" + "  ".join(f"{t.split('-')[1]}:{per_task[t]:.0%}" for t in sorted(ids, key=lambda x: int(x.split('-')[1]))))
    room = len(usable) / max(1, len(per_task))
    lines += ["", ("There is room to show an effect." if room >= 0.5 else "Most tasks are outside the 20-80% band, so this model cannot show much learning on them: the task set must be made harder (or easier) before a real run.")]
    return "\n".join(lines)
