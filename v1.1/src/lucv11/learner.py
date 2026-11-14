"""Small parametric learner for M4: shared matrix U (D x RANK) plus one head per context, logistic loss, plain SGD.
`ParamModel.step` is the ONLY place parameters change; the statistical experiment (m4.py) and the event-sourced replay (events.py) both call it,
so replaying learning events tests the real update rule."""
from __future__ import annotations

import hashlib

import numpy as np

D, RANK = 20, 4


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class ParamModel:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.U = np.random.default_rng([seed, 11]).normal(0.0, 0.3, (D, RANK))
        self.V: dict[int, np.ndarray] = {}
        self.U_anchor: np.ndarray | None = None
        self.anchor_lambda = 0.0

    def head(self, ctx: int) -> np.ndarray:
        if ctx not in self.V:
            self.V[ctx] = np.random.default_rng([self.seed, 13, ctx]).normal(0.0, 0.1, RANK)  # deterministic per (seed, context)
        return self.V[ctx]

    def logit(self, ctx: int, x: np.ndarray) -> np.ndarray:
        return x @ self.U @ self.head(ctx)

    def step(self, ctx: int, x: np.ndarray, y: float, lr: float) -> None:
        v = self.head(ctx)
        h = x @ self.U
        dz = float(sigmoid(h @ v)) - y
        grad_u = dz * np.outer(x, v)
        if self.U_anchor is not None and self.anchor_lambda:
            grad_u = grad_u + self.anchor_lambda * (self.U - self.U_anchor)
        self.U = self.U - lr * grad_u
        self.V[ctx] = v - lr * dz * h

    def snapshot_anchor(self, lam: float) -> None:
        self.U_anchor, self.anchor_lambda = self.U.copy(), lam

    def copy(self) -> "ParamModel":
        other = ParamModel(self.seed)
        other.U, other.V = self.U.copy(), {k: v.copy() for k, v in self.V.items()}
        other.U_anchor = None if self.U_anchor is None else self.U_anchor.copy()
        other.anchor_lambda = self.anchor_lambda
        return other

    def params_hash(self) -> str:
        h = hashlib.sha256(self.U.tobytes())
        for ctx in sorted(self.V):
            h.update(str(ctx).encode() + self.V[ctx].tobytes())
        return h.hexdigest()
