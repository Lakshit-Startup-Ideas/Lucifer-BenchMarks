from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..tasks import Task


@dataclass(frozen=True)
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int
    ms: float


class Backend(Protocol):
    name: str

    def generate(self, prompt: str, *, seed: int, task: Task | None = None) -> Generation: ...
