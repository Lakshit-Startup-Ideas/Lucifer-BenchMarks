"""Event-sourced learning: experience events, learning events and checkpoints are separate records on a Ledger v2 chain.
Raw experiences stay in a local store; the ledger carries only ids, hashes and parameter hashes. Logging an experience is NOT learning:
parameters change only through a `learn` event that names the experiences used and the parameter hash before and after.
Deleting a raw record does not change parameters already trained on it; unlearning here means rebuilding from a checkpoint without it."""
from __future__ import annotations

import hashlib
import json

import numpy as np

from .learner import ParamModel
from .ledger import Ledger


def content_hash(ctx: int, x: np.ndarray, y: int) -> str:
    return hashlib.sha256(str(ctx).encode() + b"|" + np.asarray(x, dtype=np.float64).tobytes() + b"|" + str(int(y)).encode()).hexdigest()


class EventSourcedLearner:
    def __init__(self, seed: int, run_id: str = "run") -> None:
        self.seed, self.run_id = seed, run_id
        self.model = ParamModel(seed)
        self.ledger = Ledger()
        self.store: dict[str, tuple[int, np.ndarray, int]] = {}  # raw experiences, local only
        self.learning: list[dict] = []
        self.checkpoints: dict[str, ParamModel] = {}
        self._n_exp = 0
        self.checkpoint("init")

    def _log(self, ident: str, kind: str, body: dict) -> None:
        self.ledger.add(ident, kind, json.dumps(body, sort_keys=True), self.run_id, self.seed)

    def observe(self, ctx: int, x: np.ndarray, y: int) -> str:
        ident = f"exp-{self._n_exp}"
        self._n_exp += 1
        self.store[ident] = (ctx, np.array(x, dtype=np.float64), int(y))
        self._log(ident, "experience", {"id": ident, "ctx": ctx, "content_sha256": content_hash(ctx, x, y)})
        return ident

    def checkpoint(self, name: str) -> None:
        self.checkpoints[name] = self.model.copy()
        self._log(name, "checkpoint", {"name": name, "params_sha256": self.model.params_hash(), "ledger_length": len(self.ledger.entries)})

    def learn(self, exp_ids: list[str], replay_ids: list[str] | None = None, lr: float = 0.1) -> dict:
        replay_ids = list(replay_ids or [])
        before = self.model.params_hash()
        for ident in list(exp_ids) + replay_ids:
            ctx, x, y = self.store[ident]
            self.model.step(ctx, x, float(y), lr)
        event = {"id": f"learn-{len(self.learning)}", "exp_ids": list(exp_ids), "replay_ids": replay_ids, "lr": lr, "before": before, "after": self.model.params_hash()}
        self.learning.append(event)
        self._log(event["id"], "learning", event)
        return event

    def rebuild(self, from_checkpoint: str = "init", skip: frozenset[str] = frozenset()) -> ParamModel:
        """Re-apply the recorded learning events to a checkpoint, leaving out the experiences in `skip`. Needs every non-skipped raw record."""
        model = self.checkpoints[from_checkpoint].copy()
        for ev in self.learning:
            for ident in [i for i in ev["exp_ids"] + ev["replay_ids"] if i not in skip]:
                ctx, x, y = self.store[ident]  # KeyError if a needed record was deleted: replay is impossible without it
                model.step(ctx, x, float(y), ev["lr"])
        return model

    def verify(self) -> bool:
        if not self.ledger.verify():
            return False
        recorded = {e.task_id: json.loads(e.text) for e in self.ledger.entries if e.kind == "experience"}
        for ident, body in recorded.items():
            if ident in self.store and content_hash(*self.store[ident]) != body["content_sha256"]:
                return False
        prev = self.checkpoints["init"].params_hash()
        for ev in self.learning:  # state-transition chain: each event starts where the previous one ended
            if ev["before"] != prev:
                return False
            prev = ev["after"]
        return prev == self.model.params_hash()
