"""POST-HOC exploratory checks, run after H4a and H4b failed (docs/M4-RESULTS.md). They cannot change the registered verdicts.
1. Replay buffer size sweep: is the replay code broken, or was the registered 100-slot buffer simply too small?
2. Descriptive final-accuracy gaps between conditions (not registered)."""
from __future__ import annotations

import json
import sys

import numpy as np

from . import m4
from .m2 import paired_ci


def main(seeds: int = 30, out_path: str | None = None) -> dict:
    out: dict = {"exploratory": True}
    base = {c: [m4.run_condition(c, s) for s in range(seeds)] for c in m4.CONDITIONS}
    col = lambda r, k: np.array([x[k] for x in r])
    out["descriptive_final_acc"] = {f"{a}_minus_{b}": paired_ci(col(base[a], "final_acc") - col(base[b], "final_acc")) for a, b in (("P", "R"), ("P+anchor", "R"), ("P+replay", "R"))}
    sweep = {}
    original = m4.REPLAY_CAPACITY
    try:
        for cap in (100, 300, 960):
            m4.REPLAY_CAPACITY = cap
            runs = [m4.run_condition("P+replay", s) for s in range(seeds)]
            sweep[str(cap)] = {"forgetting": float(col(runs, "forgetting").mean()), "final_acc": float(col(runs, "final_acc").mean()),
                               "forgetting_P_minus_replay": paired_ci(col(base["P"], "forgetting") - col(runs, "forgetting"))}
    finally:
        m4.REPLAY_CAPACITY = original
    out["replay_capacity_sweep"] = sweep
    if out_path:
        json.dump(out, open(out_path, "w"), indent=1)
    return out


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 30, sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
