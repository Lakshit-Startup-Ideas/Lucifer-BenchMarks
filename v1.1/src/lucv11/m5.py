"""M5 statistical part: when does sharing help? Personal (one model per tenant) vs pooled (one shared model), with agreeing or conflicting rules.
Registered in docs/M5-PREREGISTRATION.md."""
from __future__ import annotations

import json
import sys

import numpy as np

from .learner import D, ParamModel
from .m2 import paired_ci

CONTEXTS, TRAIN, N_TEST, EXTRA_EPOCHS, LR = 6, 60, 300, 5, 0.1


def _weights(rng: np.random.Generator) -> list[np.ndarray]:
    g = rng.normal(size=D)
    g /= np.linalg.norm(g)
    out = []
    for _ in range(CONTEXTS):
        s = np.zeros(D)
        s[rng.choice(D, 3, replace=False)] = rng.choice([-1.0, 1.0], 3)
        w = 0.5 * g + 0.5 * s / np.linalg.norm(s)
        out.append(w / np.linalg.norm(w))
    return out


def make_world(seed: int, same: bool) -> dict:
    rng = np.random.default_rng(seed)
    wa = _weights(rng)
    wb = wa if same else _weights(rng)
    tenants = []
    for w in (wa, wb):
        train = [(c, X, (X @ w[c] > 0).astype(float)) for c in range(CONTEXTS) for X in [rng.normal(size=(TRAIN, D))]]
        test = [(c, X, (X @ w[c] > 0).astype(float)) for c in range(CONTEXTS) for X in [rng.normal(size=(N_TEST, D))]]
        tenants.append({"train": train, "test": test})
    return {"tenants": tenants}


def _examples(blocks: list) -> list[tuple[int, np.ndarray, float]]:
    return [(c, X[i], y[i]) for c, X, y in blocks for i in range(len(X))]


def train_model(seed: int, examples: list, tag: int) -> ParamModel:
    rng = np.random.default_rng([seed, 21, tag])
    model = ParamModel(seed)
    order = rng.permutation(len(examples))
    for i in order:
        c, x, y = examples[i]
        model.step(c, x, y, LR)
    for _ in range(EXTRA_EPOCHS):
        for i in rng.permutation(len(examples)):
            c, x, y = examples[i]
            model.step(c, x, y, LR)
    return model


def accuracy(model: ParamModel, test: list) -> float:
    return float(np.mean([np.mean((model.logit(c, X) > 0) == y) for c, X, y in test]))


def run_world(seed: int, same: bool) -> dict:
    world = make_world(seed, same)
    ex = [_examples(t["train"]) for t in world["tenants"]]
    personal = [train_model(seed, ex[t], tag=t) for t in range(2)]
    pooled = train_model(seed, ex[0] + ex[1], tag=2)
    return {"personal": float(np.mean([accuracy(personal[t], world["tenants"][t]["test"]) for t in range(2)])),
            "pooled": float(np.mean([accuracy(pooled, world["tenants"][t]["test"]) for t in range(2)]))}


def main(seeds: int = 30, out_path: str | None = None) -> dict:
    res = {name: [run_world(s, same) for s in range(seeds)] for name, same in (("same", True), ("conflict", False))}
    diff = lambda w, a, b: np.array([r[a] - r[b] for r in res[w]])
    a = {"H5a_conflict_personal_minus_pooled": paired_ci(diff("conflict", "personal", "pooled")),
         "H5b_same_pooled_minus_personal": paired_ci(diff("same", "pooled", "personal")),
         "means": {w: {k: float(np.mean([r[k] for r in res[w]])) for k in ("personal", "pooled")} for w in res}}
    a["H5a_pass"] = bool(a["H5a_conflict_personal_minus_pooled"][0] >= 0.10 and a["H5a_conflict_personal_minus_pooled"][1] > 0.05)
    a["H5b_pass"] = bool(a["H5b_same_pooled_minus_personal"][0] >= 0.02 and a["H5b_same_pooled_minus_personal"][1] > 0)
    if out_path:
        json.dump({"analysis": a, "raw": res}, open(out_path, "w"), indent=1)
    return a


if __name__ == "__main__":
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 30, sys.argv[2] if len(sys.argv) > 2 else None), indent=1))
