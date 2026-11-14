"""M3: a hybrid executive (working memory, protected goal slot, monitor, learned estimates, cost-aware choice) in a designed simulation.
Hypotheses and the limits of what this shows: docs/M3-PREREGISTRATION.md. Control = `router`, the same worlds with every executive part off."""
from __future__ import annotations

import json
import sys
from collections import deque
from dataclasses import dataclass, replace

import numpy as np

from .m2 import paired_ci

TYPES, CAPACITY, EPISODES, DRIFT_AT = 4, 5, 300, 150
DETECT, FALSE_ALARM, ALPHA, COST_WEIGHT = 0.9, 0.05, 0.1, 0.1


@dataclass(frozen=True)
class Agent:
    name: str
    goal: bool  # protected goal slot + distractor-first eviction
    monitor: bool  # sees a (noisy) failure signal and retries
    learning: bool  # updates success estimates (needs the monitor's observations)
    conflict: bool  # cost-aware module choice


ROUTER = Agent("router", False, False, False, False)
FULL = Agent("exec-full", True, True, True, True)
AGENTS = (ROUTER, FULL, replace(FULL, name="-goal", goal=False), replace(FULL, name="-monitor", monitor=False),
          replace(FULL, name="-learning", learning=False), replace(FULL, name="-conflict", conflict=False))


@dataclass(frozen=True)
class Scenario:
    name: str
    base: float | None  # None = specialists (0.9 own type, 0.5 else)
    burst_p: float = 0.0
    drift: bool = False
    generalist: bool = False

    def _matrix(self, rot: int) -> np.ndarray:
        if self.base is not None:
            return np.full((TYPES, TYPES), self.base)
        rel = np.full((TYPES, TYPES), 0.5)
        for m in range(TYPES):
            rel[m, (m + rot) % TYPES] = 0.9
        return np.vstack([rel, np.full((1, TYPES), 0.85)]) if self.generalist else rel

    def reliability(self, episode: int) -> np.ndarray:
        return self._matrix(1 if (self.drift and episode >= DRIFT_AT) else 0)

    def prior(self) -> np.ndarray:
        """What the agents believe at the start: the pre-drift world."""
        return self._matrix(0)

    @property
    def costs(self) -> np.ndarray:
        return np.array([1.0] * TYPES + ([0.3] if self.generalist else []))


SCENARIOS = {s.name: s for s in (
    Scenario("S0-benign", 0.97), Scenario("S1-failures", None), Scenario("S2-interruptions", 0.97, burst_p=0.5),
    Scenario("S3-drift", None, drift=True), Scenario("S4-combined", None, burst_p=0.5, drift=True), Scenario("S5-cost", None, generalist=True))}


class WorkingMemory:
    def __init__(self, capacity: int, distractors_first: bool) -> None:
        self.items: deque = deque()
        self.capacity, self.distractors_first = capacity, distractors_first

    def push(self, item: tuple) -> None:
        if len(self.items) >= self.capacity:
            victim = None
            if self.distractors_first:
                victim = next((x for x in self.items if x[0] == "d"), None)
            if victim is None:
                victim = self.items[0]
            self.items.remove(victim)
        self.items.append(item)

    def has(self, item: tuple) -> bool:
        return item in self.items

    def drop(self, item: tuple) -> None:
        if item in self.items:
            self.items.remove(item)


def make_episodes(scn: Scenario, seed: int, n: int = EPISODES) -> list[dict]:
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        k = int(rng.integers(3, 6))
        out.append({"types": [int(t) for t in rng.integers(0, TYPES, k)], "bursts": [3 if rng.random() < scn.burst_p else 0 for _ in range(k)]})
    return out


def run_agent(agent: Agent, scn: Scenario, seed: int, agent_index: int = 0, detect: float = DETECT, false_alarm: float = FALSE_ALARM) -> dict:
    episodes = make_episodes(scn, seed)
    rng = np.random.default_rng(seed * 1000 + agent_index + 17)
    est = scn.prior().copy()
    costs = scn.costs
    done, cost_units, control = [], [], []
    for ep_idx, ep in enumerate(episodes):
        rel = scn.reliability(ep_idx)
        k, budget = len(ep["types"]), 2 * len(ep["types"])
        wm = WorkingMemory(CAPACITY, agent.goal)
        for j in range(k):
            wm.push(("s", j))
        ok_all, calls, spent, ctrl, distractor_id = True, 0, 0.0, 0, 0
        for j, t in enumerate(ep["types"]):
            for _ in range(ep["bursts"][j]):
                wm.push(("d", distractor_id))
                distractor_id += 1
            if not wm.has(("s", j)):
                if not agent.goal:
                    ok_all = False  # subgoal forgotten, nothing can rebuild it
                    continue
                wm.push(("s", j))
                ctrl += 1  # rebuilt from the protected goal slot
            tried: set[int] = set()
            solved = False
            while True:
                remaining = k - j - 1
                if calls >= budget or (tried and calls >= budget - remaining):  # retries keep one call per remaining subgoal
                    break
                scores = est[:, t] - (COST_WEIGHT * costs if agent.conflict else 0.0)
                scores = np.where([m in tried for m in range(len(scores))], -np.inf, scores)
                m = int(np.argmax(scores))
                if scores[m] == -np.inf:
                    break
                tried.add(m)
                calls += 1
                spent += costs[m]
                success = bool(rng.random() < rel[m, t])
                solved = solved or success
                if not agent.monitor:
                    break  # assumes success
                ctrl += 1
                observed_ok = (rng.random() >= detect) if not success else (rng.random() >= false_alarm)
                if agent.learning:
                    est[m, t] += ALPHA * (float(observed_ok) - est[m, t])
                if observed_ok:
                    break
            ok_all = ok_all and solved
            wm.drop(("s", j))
        done.append(ok_all)
        cost_units.append(spent)
        control.append(ctrl)
    done = np.array(done, dtype=float)
    return {"completion": float(done.mean()), "completion_post": float(done[DRIFT_AT:].mean()), "cost": float(np.mean(cost_units)), "control": float(np.mean(control))}


def run_all(seeds: int = 30) -> dict:
    return {s: {a.name: [run_agent(a, scn, seed, i) for seed in range(seeds)] for i, a in enumerate(AGENTS)} for s, scn in SCENARIOS.items()}


def col(res: dict, scn: str, agent: str, key: str) -> np.ndarray:
    return np.array([r[key] for r in res[scn][agent]])


def analyse(res: dict) -> dict:
    d = lambda scn, a, b, key: paired_ci(col(res, scn, a, key) - col(res, scn, b, key))
    out: dict = {}
    out["H3a_S4_full_minus_router"] = d("S4-combined", "exec-full", "router", "completion")
    out["H3a_pass"] = bool(out["H3a_S4_full_minus_router"][0] >= 0.15 and out["H3a_S4_full_minus_router"][1] > 0.10)
    out["H3b_S0_full_minus_router"] = d("S0-benign", "exec-full", "router", "completion")
    ctrl0 = (col(res, "S0-benign", "exec-full", "control").mean(), col(res, "S0-benign", "router", "control").mean())
    out["H3b_S0_control_steps_full_vs_router"] = ctrl0
    out["H3b_pass"] = bool(abs(out["H3b_S0_full_minus_router"][1]) < 0.02 and abs(out["H3b_S0_full_minus_router"][2]) < 0.02 and ctrl0[0] > ctrl0[1])
    on = {"-goal": ("S2-interruptions", "completion"), "-monitor": ("S1-failures", "completion"), "-learning": ("S3-drift", "completion_post")}
    h3c = True
    for ab, (scn, key) in on.items():
        drop = d(scn, "exec-full", ab, key)
        out[f"H3c_on_target_{ab}_{scn}"] = drop
        h3c &= bool(drop[0] >= 0.10)
    cost_gain = d("S5-cost", "-conflict", "exec-full", "cost")
    comp_drop = d("S5-cost", "exec-full", "-conflict", "completion")
    out["H3c_on_target_-conflict_S5_cost_saved"] = cost_gain
    out["H3c_on_target_-conflict_S5_completion_drop"] = comp_drop
    h3c &= bool(cost_gain[0] >= 0.5 and comp_drop[0] <= 0.03)
    for ab in ("-goal", "-monitor", "-learning", "-conflict"):
        off = d("S0-benign", "exec-full", ab, "completion")
        out[f"H3c_off_target_{ab}_S0"] = off
        h3c &= bool(off[0] < 0.02)
    out["H3c_pass"] = bool(h3c)
    out["table"] = {s: {a: {k: float(col(res, s, a, k).mean()) for k in ("completion", "completion_post", "cost", "control")} for a in res[s]} for s in res}
    return out


if __name__ == "__main__":
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    result = run_all(seeds)
    analysis = analyse(result)
    if len(sys.argv) > 2:
        json.dump({"analysis": analysis, "raw": result}, open(sys.argv[2], "w"), indent=1)
    print(json.dumps({k: v for k, v in analysis.items() if k != "table"}, indent=1))
