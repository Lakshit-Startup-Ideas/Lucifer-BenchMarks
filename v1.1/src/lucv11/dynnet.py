"""Minimal leaky recurrent network (echo-state style) that can grow and be pruned. Pure numpy, no learning of the recurrent weights.

State update:  h' = (1 - a) * h + a * tanh(W h + Win u + b)
Stability: the spectral radius of W is kept at `rho` < 1. That is the usual rule of thumb for the echo-state property, not a proof of it.
Growth keeps `rho` either by block-lower-triangular wiring (old units unchanged) or by rescaling the whole matrix (old units change).
"""
from __future__ import annotations

import numpy as np


def spectral_radius(w: np.ndarray) -> float:
    return float(np.max(np.abs(np.linalg.eigvals(w)))) if w.size else 0.0


def _sparse_normal(rng: np.random.Generator, rows: int, cols: int, density: float) -> np.ndarray:
    block = rng.standard_normal((rows, cols))
    block[rng.random((rows, cols)) > density] = 0.0
    return block


def _scale_to_radius(w: np.ndarray, rho: float) -> np.ndarray:
    radius = spectral_radius(w)
    return w * (rho / radius) if radius > 0 else w


class Reservoir:
    def __init__(self, n: int, rho: float = 0.95, leak: float = 0.3, density: float = 0.1, n_in: int = 1, seed: int = 0) -> None:
        self.rho, self.leak, self.density, self.n_in = rho, leak, density, n_in
        self.rng = np.random.default_rng(seed)
        self.W = _scale_to_radius(_sparse_normal(self.rng, n, n, density), rho)
        self.Win = self.rng.uniform(-1.0, 1.0, (n, n_in))
        self.b = self.rng.uniform(-0.1, 0.1, n)

    @property
    def n(self) -> int:
        return self.W.shape[0]

    @property
    def n_recurrent_params(self) -> int:
        return int(np.count_nonzero(self.W) + self.Win.size + self.b.size)

    def run(self, u: np.ndarray) -> np.ndarray:
        """u has shape (T, n_in). Starts from h = 0. Returns states of shape (T, n)."""
        h = np.zeros(self.n)
        out = np.empty((len(u), self.n))
        a = self.leak
        for t in range(len(u)):
            h = (1 - a) * h + a * np.tanh(self.W @ h + self.Win @ u[t] + self.b)
            out[t] = h
        return out

    def grow(self, k: int, mode: str) -> None:
        """Add k units. mode 'tri': new units listen to old units and input, old units never hear the new ones (old states unchanged).
        mode 'full': new units are wired both ways, then the whole matrix is rescaled to radius rho (old states change)."""
        n = self.n
        new_in = _sparse_normal(self.rng, k, k, self.density)
        from_old = _sparse_normal(self.rng, k, n, self.density)
        to_old = np.zeros((n, k)) if mode == "tri" else _sparse_normal(self.rng, n, k, self.density)
        if mode == "tri":
            new_in = _scale_to_radius(new_in, self.rho)
        elif mode != "full":
            raise ValueError(f"unknown growth mode {mode!r}")
        w = np.block([[self.W, to_old], [from_old, new_in]])
        self.W = _scale_to_radius(w, self.rho) if mode == "full" else w
        self.Win = np.vstack([self.Win, self.rng.uniform(-1.0, 1.0, (k, self.n_in))])
        self.b = np.concatenate([self.b, self.rng.uniform(-0.1, 0.1, k)])

    def keep(self, idx: np.ndarray) -> None:
        """Pruning: keep only the units in idx (in order). Radius can only change; it is renormalised if it exceeds rho."""
        idx = np.sort(np.asarray(idx))
        self.W, self.Win, self.b = self.W[np.ix_(idx, idx)], self.Win[idx], self.b[idx]
        if spectral_radius(self.W) > self.rho:
            self.W = _scale_to_radius(self.W, self.rho)


class Head:
    """One linear readout, fitted once by ridge regression on a (washed-out) state matrix. Includes a bias."""

    def __init__(self, weights: np.ndarray) -> None:
        self.w = weights  # shape (n + 1,)

    @staticmethod
    def fit(states: np.ndarray, y: np.ndarray, ridge: float = 1e-4) -> "Head":
        x = np.hstack([states, np.ones((len(states), 1))])
        a = x.T @ x + ridge * np.eye(x.shape[1])
        return Head(np.linalg.solve(a, x.T @ y))

    def predict(self, states: np.ndarray) -> np.ndarray:
        n_head = len(self.w) - 1
        # Units added after this head was fitted get weight 0, so a head ignores units it never saw.
        x = np.hstack([states[:, :n_head], np.ones((len(states), 1))])
        return x @ self.w


def nmse(pred: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((pred - y) ** 2) / np.var(y))
