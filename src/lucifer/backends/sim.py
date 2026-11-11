"""Simulated agents with a KNOWN answer, used only to test the measuring machinery (never to claim anything about real models).

 - null:    memory makes no difference to it.
 - learner: a relevant lesson in the notes raises its chance of a correct first attempt.
 - harmful: any notes at all lower its chance (a stand-in for a small model confused by extra text).

A "correct" reply is the task's reference code and a "wrong" one is its naive code, so everything downstream (retries, tests, memory,
statistics) runs exactly as it would for a real model.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ..agent import NOTES_HEADER, RETRY_MARKER
from ..tasks import FAMILIES, TASKS, Task
from .base import Generation


@dataclass
class SimBackend:
    kind: str = "learner"  # null | learner | harmful
    base: float = 0.4
    effect: float = 0.4
    retry_success: float = 0.85

    def __post_init__(self) -> None:
        if self.kind not in ("null", "learner", "harmful"):
            raise ValueError(f"unknown simulated agent: {self.kind}")
        self.name = f"sim-{self.kind}"

    def _uniform(self, prompt: str, seed: int, task: Task) -> float:
        digest = hashlib.sha256(f"{seed}|{task.id}|{prompt}".encode()).digest()
        return int.from_bytes(digest[:8], "big") / 2**64

    def generate(self, prompt: str, *, seed: int, task: Task | None = None) -> Generation:
        assert task is not None, "simulated agents need the task"
        if RETRY_MARKER in prompt:
            p = self.retry_success
        else:
            p = self.base
            notes = prompt.split(NOTES_HEADER, 1)[1].split("Write a Python function", 1)[0].lower() if NOTES_HEADER in prompt else ""
            if self.kind == "learner" and notes:
                seen = {f for f in FAMILIES if any(t.spec.lower() in notes for t in TASKS if t.family == f and t.split == "exp")}
                if task.family == "mixed":  # transfer: partial help, in proportion to how many pitfalls were learned
                    p += self.effect * len(seen) / len(FAMILIES)
                elif task.family in seen:  # a lesson from this task's own pitfall family is in the notes
                    p += self.effect
            elif self.kind == "harmful" and notes:
                p -= self.effect
        p = min(0.98, max(0.02, p))
        code = task.reference if self._uniform(prompt, seed, task) < p else task.naive
        # A made-up but deterministic latency (about 0.4 to 1.4 s, longer for longer prompts); spans mark it as simulated.
        latency = 400 + 1000 * self._uniform("latency|" + prompt, seed, task) * min(1.0, len(prompt) / 1500 + 0.3)
        return Generation(f"```python\n{code}\n```", len(prompt) // 4, len(code) // 4, round(latency, 1))
