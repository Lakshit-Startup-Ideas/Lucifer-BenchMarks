"""M2 experiment: fixed vs growing recurrent networks on a sequence of delay-recall tasks. Hypotheses: docs/M2-PREREGISTRATION.md."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field

import numpy as np

from .dynnet import Head, Reservoir, nmse

DELAYS = (5, 15, 30)
TRAIN, TEST, WASHOUT = 2000, 1000, 100
HOLDOUT = 0.25
GROW_THRESHOLD, GROW_STEP, N_START, N_MAX = 0.10, 40, 40, 160
CONDITIONS = ("fixed-small", "fixed-large", "grow-tri", "grow-full")


def make_task(delay: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    out = {}
    for split, t in (("train", TRAIN), ("test", TEST)):
        u = rng.uniform(-0.5, 0.5, (t + delay, 1))
        out[split] = (u[delay:], u[:t, 0])  # y[t] = u[t - delay]; inputs aligned so y is the delayed copy
    return out


def _states(net: Reservoir, u: np.ndarray, counter: list) -> np.ndarray:
    counter[0] += len(u) * net.n
    return net.run(u)


@dataclass
class Result:
    condition: str
    seed: int
    nmse_after_training: list = field(default_factory=list)  # each task, right after its head was fitted
    nmse_final: list = field(default_factory=list)  # each task, after all tasks were learned
    units: int = 0
    unit_steps: int = 0
    params: int = 0


def run_condition(condition: str, seed: int) -> Result:
    n0 = {"fixed-small": N_START, "fixed-large": N_MAX}.get(condition, N_START)
    net = Reservoir(n0, seed=1000 + seed)
    tasks = [make_task(d, seed * 10 + i) for i, d in enumerate(DELAYS)]
    heads: list[Head] = []
    steps = [0]
    res = Result(condition, seed)
    split = int(TRAIN * (1 - HOLDOUT))
    for task in tasks:
        u, y = task["train"]
        while True:
            s = _states(net, u, steps)
            head = Head.fit(s[WASHOUT:split], y[WASHOUT:split])
            val = nmse(head.predict(s[split:]), y[split:])
            if condition.startswith("grow") and val > GROW_THRESHOLD and net.n < N_MAX:
                net.grow(GROW_STEP, "tri" if condition == "grow-tri" else "full")
                continue
            break
        heads.append(head)
        ut, yt = task["test"]
        res.nmse_after_training.append(nmse(head.predict(_states(net, ut, steps)[WASHOUT:]), yt[WASHOUT:]))
    for head, task in zip(heads, tasks):
        ut, yt = task["test"]
        res.nmse_final.append(nmse(head.predict(_states(net, ut, steps)[WASHOUT:]), yt[WASHOUT:]))
    res.units, res.unit_steps = net.n, steps[0]
    res.params = net.n_recurrent_params + sum(len(h.w) for h in heads)
    return res


def prune_experiment(seed: int) -> dict:
    """Single task (delay 15), 160 units. Prune to 80 by importance or at random, refit the head, compare test NMSE."""
    task = make_task(15, seed * 10 + 1)
    base = Reservoir(N_MAX, seed=2000 + seed)
    u, y = task["train"]
    ut, yt = task["test"]
    s = base.run(u)
    head = Head.fit(s[WASHOUT:], y[WASHOUT:])
    full = nmse(head.predict(base.run(ut)[WASHOUT:]), yt[WASHOUT:])
    importance = np.abs(head.w[:-1]) * s[WASHOUT:].std(axis=0)
    rng = np.random.default_rng(3000 + seed)
    out = {"full": full}
    for name, idx in (("importance", np.argsort(importance)[-N_MAX // 2:]), ("random", rng.choice(N_MAX, N_MAX // 2, replace=False))):
        net = Reservoir(N_MAX, seed=2000 + seed)
        net.keep(idx)
        h2 = Head.fit(net.run(u)[WASHOUT:], y[WASHOUT:])
        out[name] = nmse(h2.predict(net.run(ut)[WASHOUT:]), yt[WASHOUT:])
    return out


def paired_ci(diff: np.ndarray, resamples: int = 10_000, seed: int = 0) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    means = np.array([rng.choice(diff, len(diff)).mean() for _ in range(resamples)])
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def analyse(results: dict[str, list[Result]], prunes: list[dict]) -> dict:
    def col(cond, attr, task=None):
        return np.array([getattr(r, attr)[task] if task is not None else getattr(r, attr) for r in results[cond]])

    forget = lambda cond: np.array([np.mean([r.nmse_final[i] - r.nmse_after_training[i] for i in range(len(DELAYS) - 1)]) for r in results[cond]])
    tri_change = max(abs(f - a) for r in results["grow-tri"] for f, a in zip(r.nmse_final, r.nmse_after_training))
    last = len(DELAYS) - 1
    a = {
        "H2a_tri_max_abs_change": float(tri_change),
        "H2a_pass": bool(tri_change < 1e-9),
        "H2b_full_mean_forgetting": paired_ci(forget("grow-full")),
        "H2b_pass": bool(forget("grow-full").mean() > 0.05),
        "H2c_tri_minus_large_last_task_nmse": paired_ci(col("grow-tri", "nmse_final", last) - col("fixed-large", "nmse_final", last)),
        "H2d_tri_minus_large_unit_steps": paired_ci(col("grow-tri", "unit_steps") - col("fixed-large", "unit_steps")),
        "H2e_tri_minus_small_last_task_nmse": paired_ci(col("grow-tri", "nmse_final", last) - col("fixed-small", "nmse_final", last)),
        "H2f_prune_importance_minus_full": paired_ci(np.array([p["importance"] - p["full"] for p in prunes])),
        "H2f_prune_importance_minus_random": paired_ci(np.array([p["importance"] - p["random"] for p in prunes])),
    }
    a["H2c_pass"] = bool(a["H2c_tri_minus_large_last_task_nmse"][2] < 0.02)
    a["H2d_pass"] = bool(a["H2d_tri_minus_large_unit_steps"][2] < 0)
    a["H2e_pass"] = bool(a["H2e_tri_minus_small_last_task_nmse"][2] < 0)
    a["H2f_pass"] = bool(a["H2f_prune_importance_minus_full"][0] <= 0.05 and a["H2f_prune_importance_minus_random"][2] < 0)
    a["summary"] = {c: {"units": float(col(c, "units").mean()), "unit_steps": float(col(c, "unit_steps").mean()), "params": float(col(c, "params").mean()),
                        "nmse_final_by_task": [float(col(c, "nmse_final", i).mean()) for i in range(len(DELAYS))],
                        "nmse_after_training_by_task": [float(col(c, "nmse_after_training", i).mean()) for i in range(len(DELAYS))]} for c in CONDITIONS}
    return a


def main(seeds: int = 20, out_path: str | None = None) -> dict:
    results = {c: [run_condition(c, s) for s in range(seeds)] for c in CONDITIONS}
    prunes = [prune_experiment(s) for s in range(seeds)]
    analysis = analyse(results, prunes)
    if out_path:
        raw = {c: [r.__dict__ for r in rs] for c, rs in results.items()}
        with open(out_path, "w") as f:
            json.dump({"analysis": analysis, "raw": raw, "prunes": prunes}, f, indent=1)
    return analysis


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 20, sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
