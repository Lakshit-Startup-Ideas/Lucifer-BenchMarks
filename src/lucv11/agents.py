"""M7 agent runtime: lifecycle, task execution with retries and backoff, and crash recovery from a Ledger v2 event log.
A task that finished is never executed again (idempotency key). The result store here is in memory; a real system must persist it with the log."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .ledger import Ledger
from .tools import CallResult, ToolEngine

TRANSITIONS = {"created": {"running", "stopped"}, "running": {"stopped", "failed"}, "failed": {"stopped", "running"}, "stopped": set()}
RETRYABLE = {"timeout", "handler_error", "rate_limited"}


@dataclass
class Task:
    id: str
    tool: str
    args: dict
    idempotency_key: str
    max_attempts: int = 3
    attempts: int = 0
    not_before: float = 0.0
    status: str = "queued"  # queued | completed | failed
    result: str = ""


class Runtime:
    def __init__(self, engine: ToolEngine, agent_id: str, clock: Callable[[], float], backoff_s: float = 1.0, ledger: Ledger | None = None,
                 results: dict[str, str] | None = None) -> None:
        self.engine, self.agent_id, self.clock, self.backoff_s = engine, agent_id, clock, backoff_s
        self.ledger = ledger or Ledger()
        self.results = results if results is not None else {}  # idempotency key -> result text (must be persisted for real recovery)
        self.state = "created"
        self.queue: list[Task] = []

    def _log(self, kind: str, body: dict) -> None:
        self.ledger.add(body.get("id", "runtime"), kind, json.dumps(body, sort_keys=True), self.agent_id, 0)

    def transition(self, new: str) -> None:
        if new not in TRANSITIONS[self.state]:
            raise ValueError(f"illegal transition {self.state} -> {new}")
        self._log("lifecycle", {"id": "runtime", "from": self.state, "to": new})
        self.state = new

    def submit(self, task: Task) -> None:
        self._log("task-submitted", {"id": task.id, "tool": task.tool, "idempotency_key": task.idempotency_key, "max_attempts": task.max_attempts, "args": task.args})
        self.queue.append(task)

    def run_pending(self) -> int:
        """Run every task that is due; returns how many reached a final state. Retries are rescheduled with exponential backoff."""
        if self.state != "running":
            raise ValueError("runtime is not running")
        done = 0
        for task in list(self.queue):
            if task.status != "queued" or task.not_before > self.clock():
                continue
            if task.idempotency_key in self.results:  # finished before (possibly before a crash): do not run again
                task.status, task.result = "completed", self.results[task.idempotency_key]
                self._log("task-skipped-duplicate", {"id": task.id})
                done += 1
                continue
            task.attempts += 1
            res: CallResult = self.engine.call(self.agent_id, task.tool, task.args)
            if res.ok:
                self.results[task.idempotency_key] = res.text
                task.status, task.result = "completed", res.text
                self._log("task-completed", {"id": task.id, "attempts": task.attempts})
                done += 1
            elif res.code in RETRYABLE and task.attempts < task.max_attempts:
                task.not_before = self.clock() + self.backoff_s * 2 ** (task.attempts - 1)
                self._log("task-retry", {"id": task.id, "attempts": task.attempts, "code": res.code, "not_before": task.not_before})
            else:
                task.status = "failed"
                self._log("task-failed", {"id": task.id, "attempts": task.attempts, "code": res.code})
                done += 1
        return done

    @classmethod
    def recover(cls, engine: ToolEngine, agent_id: str, clock: Callable[[], float], ledger: Ledger, results: dict[str, str], backoff_s: float = 1.0) -> "Runtime":
        """Rebuild the queue from the event log: tasks submitted but neither completed nor failed run again; finished ones stay finished."""
        runtime = cls(engine, agent_id, clock, backoff_s, ledger=ledger, results=results)
        finished, submitted = set(), {}
        for e in ledger.entries:
            body = json.loads(e.text)
            if e.kind == "task-submitted":
                submitted[body["id"]] = body
            elif e.kind in ("task-completed", "task-failed", "task-skipped-duplicate"):
                finished.add(body["id"])
        runtime.state = "created"
        runtime.queue = [Task(b["id"], b["tool"], b["args"], b["idempotency_key"], b["max_attempts"]) for i, b in submitted.items() if i not in finished]
        return runtime
