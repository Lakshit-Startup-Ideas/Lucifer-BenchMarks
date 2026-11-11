"""Small, dependency-free statistics: task-level means and a paired bootstrap for the difference between two conditions."""
from __future__ import annotations

import random
from collections import defaultdict
from statistics import fmean

PRIMARY_PHASES = ("similar", "transfer")


def task_means(rows: list[dict], condition: str, phases: tuple[str, ...] = PRIMARY_PHASES, metric: str = "pass_at_1") -> dict[str, float]:
    """The metric averaged over seeds, per task. The task (not the seed) is the unit we bootstrap over."""
    by_task: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r["condition"] == condition and r["phase"] in phases:
            by_task[r["task_id"]].append(1.0 if r[metric] else 0.0)
    return {t: fmean(v) for t, v in by_task.items()}


def paired_bootstrap(a: dict[str, float], b: dict[str, float], resamples: int = 10_000, seed: int = 0) -> tuple[float, float, float]:
    """Mean of (b - a) over shared tasks, with a 95% interval from resampling tasks. Returns (mean, low, high)."""
    tasks = sorted(set(a) & set(b))
    if not tasks:
        return 0.0, 0.0, 0.0
    diffs = [b[t] - a[t] for t in tasks]
    rng = random.Random(seed)
    n = len(diffs)
    means = sorted(fmean(rng.choices(diffs, k=n)) for _ in range(resamples))
    return fmean(diffs), means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]
