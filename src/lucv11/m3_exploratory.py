"""POST-HOC exploratory check, run after H3b failed (docs/M3-RESULTS.md). It cannot change the registered verdicts.
A failure-free world (reliability exactly 1.0, no interruptions, no drift): the executive should add nothing but overhead."""
from __future__ import annotations

import json
import sys

import numpy as np

from .m2 import paired_ci
from .m3 import AGENTS, Scenario, run_agent


def main(seeds: int = 30, out_path: str | None = None) -> dict:
    scn = Scenario("X0-perfect", 1.0)
    res = {a.name: [run_agent(a, scn, s, i) for s in range(seeds)] for i, a in enumerate(AGENTS)}
    col = lambda a, k: np.array([r[k] for r in res[a]])
    out: dict = {"exploratory": True, "scenario": "X0-perfect (post-hoc, after H3b failed)"}
    for a in AGENTS[1:]:
        out[f"completion_{a.name}_minus_router"] = paired_ci(col(a.name, "completion") - col("router", "completion"))
    out["control_steps_per_episode"] = {a.name: float(col(a.name, "control").mean()) for a in AGENTS}
    out["cost_units_per_episode"] = {a.name: float(col(a.name, "cost").mean()) for a in AGENTS}
    if out_path:
        json.dump(out, open(out_path, "w"), indent=1)
    return out


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 30, sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
