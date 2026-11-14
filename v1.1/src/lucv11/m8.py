"""M8: the two hypotheses no earlier milestone tested. H8 maturation (falling plasticity, rising consolidation with developmental age) and
H9 experience on unseen task families. Registered in docs/M8-PREREGISTRATION.md. Uses the M4 world and learner; the `anchor` control reproduces M4's P+anchor."""
from __future__ import annotations

import json
import sys
from typing import Callable

import numpy as np

from . import m4
from .learner import D, ParamModel
from .m2 import paired_ci

T_MAX = m4.CONTEXTS - 1
SAME_FAMILY, UNSEEN_FAMILY, NEW_PER_GROUP, NEW_EXAMPLES, FIRST = 4, 4, 4, 80, 40


def lr_constant(t: int) -> float:
    return 0.1


def lam_constant(t: int) -> float:
    return 1.0


def lr_mature(t: int) -> float:
    return 0.2 * 0.25 ** (t / T_MAX)


def lam_mature(t: int) -> float:
    return 0.5 + 1.5 * t / T_MAX


def run_schedule(seed: int, lr_fn: Callable[[int], float], lam_fn: Callable[[int], float]) -> dict:
    """The M4 `P+anchor` procedure with a per-phase learning rate and anchor strength (age t = phase index)."""
    world = m4.make_world(seed)
    rng = np.random.default_rng([seed, 5, m4.CONDITIONS.index("P+anchor")])  # same stream as m4.run_condition("P+anchor")
    model = ParamModel(seed)
    acc = np.full((m4.CONTEXTS, m4.CONTEXTS), np.nan)
    for c in range(m4.CONTEXTS):
        X, Y = world["train"][c]
        lr = lr_fn(c)
        for i in range(m4.PER_PHASE):
            model.step(c, X[i], Y[i], lr)
        for _ in range(m4.EXTRA_EPOCHS):
            for i in rng.permutation(m4.PER_PHASE):
                model.step(c, X[i], Y[i], lr)
        model.snapshot_anchor(lam_fn(c))
        for k in range(c + 1):
            Xt, Yt = world["test"][k]
            acc[c, k] = float(np.mean((model.logit(k, Xt) > 0) == Yt))
    return {"final_acc": float(np.mean(acc[-1])), "forgetting": float(np.mean([np.nanmax(acc[k:, k]) - acc[-1, k] for k in range(m4.CONTEXTS - 1)]))}


def _rules(rng: np.random.Generator, g: np.ndarray, n: int) -> list[np.ndarray]:
    out = []
    for _ in range(n):
        s = np.zeros(D)
        s[rng.choice(D, 3, replace=False)] = rng.choice([-1.0, 1.0], 3)
        w = 0.5 * g + 0.5 * s / np.linalg.norm(s)
        out.append(w / np.linalg.norm(w))
    return out


def _unit(rng: np.random.Generator) -> np.ndarray:
    g = rng.normal(size=D)
    return g / np.linalg.norm(g)


def run_families(seed: int) -> dict:
    rng = np.random.default_rng([seed, 99])
    g1, g2 = _unit(rng), _unit(rng)
    train_rules = _rules(rng, g1, m4.CONTEXTS)
    groups = {"same": _rules(rng, g1, SAME_FAMILY), "unseen": _rules(rng, g2, UNSEEN_FAMILY)}
    experienced = ParamModel(seed)
    for c, w in enumerate(train_rules):
        X = rng.normal(size=(m4.PER_PHASE, D))
        Y = (X @ w > 0).astype(float)
        for i in range(m4.PER_PHASE):
            experienced.step(c, X[i], Y[i], 0.1)
        for _ in range(m4.EXTRA_EPOCHS):
            for i in rng.permutation(m4.PER_PHASE):
                experienced.step(c, X[i], Y[i], 0.1)
        experienced.snapshot_anchor(1.0)
    before = experienced.params_hash()
    fresh_template = ParamModel(seed)
    result: dict = {}
    for name, rules in groups.items():
        scores = {"experienced": [], "fresh": []}
        for j, w in enumerate(rules):
            ctx = 100 + j  # new context ids: heads start fresh in both models
            X = rng.normal(size=(NEW_EXAMPLES, D))
            Y = (X @ w > 0).astype(float)
            for label, base in (("experienced", experienced), ("fresh", fresh_template)):
                m = base.copy()
                m.U_anchor, m.anchor_lambda = None, 0.0  # measure raw learning speed, no anchor
                correct = []
                for i in range(NEW_EXAMPLES):
                    correct.append(float((m.logit(ctx, X[i]) > 0) == Y[i]))
                    m.step(ctx, X[i], Y[i], 0.1)
                scores[label].append(float(np.mean(correct[:FIRST])))
        result[name] = {k: float(np.mean(v)) for k, v in scores.items()}
    assert experienced.params_hash() == before  # measuring never changes the experienced model
    return result


def analyse(maturation: dict, families: dict) -> dict:
    col = lambda runs, k: np.array([r[k] for r in runs])
    a: dict = {}
    a["H8_forgetting_anchor_minus_mature"] = paired_ci(col(maturation["anchor"], "forgetting") - col(maturation["mature"], "forgetting"))
    a["H8_final_acc_mature_minus_anchor"] = paired_ci(col(maturation["mature"], "final_acc") - col(maturation["anchor"], "final_acc"))
    a["H8_means"] = {k: {m: float(col(v, m).mean()) for m in ("final_acc", "forgetting")} for k, v in maturation.items()}
    a["H8_pass"] = bool(a["H8_forgetting_anchor_minus_mature"][0] >= 0.01 and a["H8_forgetting_anchor_minus_mature"][1] > 0 and a["H8_final_acc_mature_minus_anchor"][0] >= -0.01)
    diff = lambda g: np.array([r[g]["experienced"] - r[g]["fresh"] for r in families])
    a["H9a_same_family_experienced_minus_fresh"] = paired_ci(diff("same"))
    a["H9b_unseen_family_experienced_minus_fresh"] = paired_ci(diff("unseen"))
    a["H9a_pass"] = bool(a["H9a_same_family_experienced_minus_fresh"][0] >= 0.05 and a["H9a_same_family_experienced_minus_fresh"][1] > 0.02)
    a["H9b_pass"] = bool(a["H9b_unseen_family_experienced_minus_fresh"][1] > -0.03)
    a["H9_pass"] = a["H9a_pass"] and a["H9b_pass"]
    a["H9_means"] = {g: {k: float(np.mean([r[g][k] for r in families])) for k in ("experienced", "fresh")} for g in ("same", "unseen")}
    return a


def main(seeds: int = 30, out_path: str | None = None) -> dict:
    maturation = {"anchor": [run_schedule(s, lr_constant, lam_constant) for s in range(seeds)], "mature": [run_schedule(s, lr_mature, lam_mature) for s in range(seeds)]}
    families = [run_families(s) for s in range(seeds)]
    analysis = analyse(maturation, families)
    if out_path:
        json.dump({"analysis": analysis, "raw": {"maturation": maturation, "families": families}}, open(out_path, "w"), indent=1)
    return analysis


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 30, sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
