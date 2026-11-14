"""M4: retrieval vs parameter adaptation vs protection against forgetting on a stream of 12 contexts. Registered in docs/M4-PREREGISTRATION.md."""
from __future__ import annotations

import json
import sys

import numpy as np

from .learner import D, ParamModel
from .m2 import paired_ci

CONTEXTS, PER_PHASE, N_TEST, EXTRA_EPOCHS, LR = 12, 80, 300, 5, 0.1
REPLAY_CAPACITY, REPLAY_BATCH, ANCHOR_LAMBDA, KNN = 100, 8, 1.0, 5
CONDITIONS = ("R", "P", "P+replay", "P+anchor")
EARLY, LATE = range(0, 3), range(8, 12)  # contexts 1-3 and 9-12


def make_world(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    g = rng.normal(size=D)
    g /= np.linalg.norm(g)
    weights = []
    for _ in range(CONTEXTS):
        s = np.zeros(D)
        s[rng.choice(D, 3, replace=False)] = rng.choice([-1.0, 1.0], 3)
        w = 0.5 * g + 0.5 * s / np.linalg.norm(s)
        weights.append(w / np.linalg.norm(w))
    train = [rng.normal(size=(PER_PHASE, D)) for _ in range(CONTEXTS)]
    test = [rng.normal(size=(N_TEST, D)) for _ in range(CONTEXTS)]
    label = lambda c, X: (X @ weights[c] > 0).astype(float)
    return {"train": [(X, label(c, X)) for c, X in enumerate(train)], "test": [(X, label(c, X)) for c, X in enumerate(test)]}


def knn_predict(store_x: list, store_y: list, x: np.ndarray, rng: np.random.Generator) -> float:
    if not store_x:
        return float(rng.integers(0, 2))
    d = np.linalg.norm(np.array(store_x) - x, axis=1)
    idx = np.argsort(d)[:KNN]
    return float(np.mean([store_y[i] for i in idx]) >= 0.5)


def run_condition(cond: str, seed: int) -> dict:
    world = make_world(seed)
    rng = np.random.default_rng([seed, 5, CONDITIONS.index(cond)])
    model = ParamModel(seed)
    memory: dict[int, tuple[list, list]] = {}
    reservoir: list[tuple[int, np.ndarray, float]] = []
    seen_total = 0
    acc = np.full((CONTEXTS, CONTEXTS), np.nan)
    first10 = []

    def train_step(c, x, y):
        model.step(c, x, y, LR)
        if cond == "P+replay" and reservoir:
            for i in rng.choice(len(reservoir), min(REPLAY_BATCH, len(reservoir)), replace=False):
                rc, rx, ry = reservoir[i]
                model.step(rc, rx, ry, LR)

    for c in range(CONTEXTS):
        X, Y = world["train"][c]
        online = []
        for i in range(PER_PHASE):
            x, y = X[i], Y[i]
            if cond == "R":
                pred = knn_predict(*memory.get(c, ([], [])), x, rng)
                memory.setdefault(c, ([], []))[0].append(x)
                memory[c][1].append(y)
            else:
                pred = float(model.logit(c, x) > 0)
                train_step(c, x, y)
                if cond == "P+replay":
                    seen_total += 1
                    if len(reservoir) < REPLAY_CAPACITY:
                        reservoir.append((c, x, y))
                    elif (j := rng.integers(0, seen_total)) < REPLAY_CAPACITY:
                        reservoir[j] = (c, x, y)
            online.append(float(pred == y))
        first10.append(float(np.mean(online[:10])))
        if cond != "R":
            for _ in range(EXTRA_EPOCHS):
                for i in rng.permutation(PER_PHASE):
                    train_step(c, X[i], Y[i])
            if cond == "P+anchor":
                model.snapshot_anchor(ANCHOR_LAMBDA)
        for k in range(c + 1):
            Xt, Yt = world["test"][k]
            if cond == "R":
                sx, sy = memory[k]
                pred = np.array([knn_predict(sx, sy, x, rng) for x in Xt])
            else:
                pred = (model.logit(k, Xt) > 0).astype(float)
            acc[c, k] = float(np.mean(pred == Yt))
    forgetting = float(np.mean([np.nanmax(acc[k:, k]) - acc[-1, k] for k in range(CONTEXTS - 1)]))
    storage = sum(len(v[0]) for v in memory.values()) if cond == "R" else (len(reservoir) if cond == "P+replay" else 0)
    return {"final_acc": float(np.mean(acc[-1])), "forgetting": forgetting, "fs_early": float(np.mean([first10[c] for c in EARLY])),
            "fs_late": float(np.mean([first10[c] for c in LATE])), "storage": storage}


def run_all(seeds: int = 30) -> dict:
    return {c: [run_condition(c, s) for s in range(seeds)] for c in CONDITIONS}


def analyse(res: dict) -> dict:
    col = lambda c, k: np.array([r[k] for r in res[c]])
    d = lambda a, b, k: paired_ci(col(a, k) - col(b, k))
    a: dict = {}
    a["precondition_P_forgetting"] = float(col("P", "forgetting").mean())
    a["precondition_pass"] = a["precondition_P_forgetting"] >= 0.05
    a["H4a_i_P_minus_R_fewshot_late"] = d("P", "R", "fs_late")
    a["H4a_ii_P_late_minus_early"] = paired_ci(col("P", "fs_late") - col("P", "fs_early"))
    a["H4a_iii_R_late_minus_early"] = paired_ci(col("R", "fs_late") - col("R", "fs_early"))
    a["H4a_pass"] = bool(a["H4a_i_P_minus_R_fewshot_late"][0] >= 0.10 and a["H4a_i_P_minus_R_fewshot_late"][1] > 0.05
                         and a["H4a_ii_P_late_minus_early"][0] >= 0.10 and a["H4a_ii_P_late_minus_early"][1] > 0.05
                         and a["H4a_iii_R_late_minus_early"][1] > -0.03 and a["H4a_iii_R_late_minus_early"][2] < 0.03)
    a["H4b_forgetting_P_minus_replay"] = d("P", "P+replay", "forgetting")
    a["H4b_pass"] = bool(a["precondition_pass"] and a["H4b_forgetting_P_minus_replay"][0] >= 0.05 and a["H4b_forgetting_P_minus_replay"][1] > 0)
    a["H4c_forgetting_P_minus_anchor"] = d("P", "P+anchor", "forgetting")
    a["H4c_final_acc_anchor_minus_P"] = d("P+anchor", "P", "final_acc")
    a["H4c_pass"] = bool(a["precondition_pass"] and a["H4c_forgetting_P_minus_anchor"][0] >= 0.05 and a["H4c_forgetting_P_minus_anchor"][1] > 0
                         and a["H4c_final_acc_anchor_minus_P"][0] >= -0.03)
    a["H4d_table"] = {c: {k: float(col(c, k).mean()) for k in ("final_acc", "forgetting", "fs_early", "fs_late", "storage")} for c in CONDITIONS}
    return a


if __name__ == "__main__":
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    res = run_all(seeds)
    analysis = analyse(res)
    if len(sys.argv) > 2:
        json.dump({"analysis": analysis, "raw": res}, open(sys.argv[2], "w"), indent=1)
    print(json.dumps(analysis, indent=1))
