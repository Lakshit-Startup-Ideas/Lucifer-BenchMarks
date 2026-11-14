"""M7 A2A MODEL: an in-process model of agent cards, capability negotiation and the v0.3.0 task lifecycle (lowercase states). It is NOT wire-compatible
with any A2A version, and the card path below is unverified against an official page. Registered in docs/M7-PREREGISTRATION.md."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from typing import Callable

from .ledger import Ledger

CARD_PATH = "/.well-known/agent-card.json"  # configurable and UNVERIFIED (taken from a third-party issue, not an official page)
TERMINAL = {"completed", "canceled", "failed", "rejected"}
ALLOWED = {"submitted": {"working", "rejected", "canceled", "failed", "auth-required"},
           "working": {"completed", "failed", "canceled", "input-required", "auth-required"},
           "input-required": {"working", "canceled", "failed"}, "auth-required": {"working", "canceled", "failed", "rejected"}}
MAX_MESSAGE = 2000


@dataclass(frozen=True)
class AgentCard:
    name: str
    description: str
    version: str
    skills: tuple[str, ...]
    auth: str = "hmac-sha256"


@dataclass
class A2ATask:
    id: str
    owner: str
    skill: str
    state: str = "submitted"
    result: str = ""


class InputRequired(Exception):
    pass


def sign(key: bytes, peer: str, seq: int, skill: str, message: str) -> str:
    body = json.dumps({"peer": peer, "seq": seq, "skill": skill, "message": message}, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(key, body, hashlib.sha256).hexdigest()


class A2AServer:
    def __init__(self, card: AgentCard, handlers: dict[str, Callable[[str], str]]) -> None:
        if set(card.skills) != set(handlers):
            raise ValueError("card skills must match handlers")
        self.card, self.handlers = card, handlers
        self.tasks: dict[str, A2ATask] = {}
        self.ledger = Ledger()
        self._peers: dict[str, tuple[bytes, frozenset]] = {}
        self._seq: dict[str, int] = {}

    def register_peer(self, peer_id: str, allowed_skills: set[str]) -> bytes:
        key = secrets.token_bytes(32)
        self._peers[peer_id] = (key, frozenset(allowed_skills))
        return key

    def _log(self, ident: str, kind: str, body: dict) -> None:
        self.ledger.add(ident, kind, json.dumps(body, sort_keys=True), "a2a", 0)

    def _move(self, task: A2ATask, new: str) -> None:
        if task.state in TERMINAL or new not in ALLOWED.get(task.state, set()):
            raise ValueError(f"illegal transition {task.state} -> {new}")
        self._log(task.id, "task-state", {"from": task.state, "to": new})
        task.state = new

    def send_task(self, peer: str, seq: int, skill: str, message: str, mac: str) -> dict:
        """Authenticated, replay-protected task submission. The callee sees only `message`; nothing about the caller's tools or credentials."""
        record = self._peers.get(peer) if isinstance(peer, str) else None
        if record is None or not isinstance(seq, int) or isinstance(seq, bool) or not isinstance(skill, str) or not isinstance(message, str) or not isinstance(mac, str):
            self._log("rejected", "rejection", {"reason": "unknown or malformed"})
            return {"error": "unauthenticated"}
        key, allowed = record
        if not hmac.compare_digest(sign(key, peer, seq, skill, message), mac):
            self._log("rejected", "rejection", {"reason": "bad mac"})
            return {"error": "unauthenticated"}
        if seq <= self._seq.get(peer, 0):
            self._log("rejected", "rejection", {"reason": "replay"})
            return {"error": "replay"}
        self._seq[peer] = seq
        if len(message) > MAX_MESSAGE:
            return {"error": "message too large"}
        task = A2ATask(f"task-{len(self.tasks) + 1}", peer, skill)
        self.tasks[task.id] = task
        self._log(task.id, "task-submitted", {"peer": peer, "skill": skill})
        if skill not in self.handlers or skill not in allowed:
            self._move(task, "rejected")  # same answer for "no such skill" and "not permitted"
            return {"id": task.id, "state": task.state}
        self._move(task, "working")
        try:
            task.result = self.handlers[skill](message)
            self._move(task, "completed")
        except InputRequired:
            self._move(task, "input-required")
        except Exception:
            self._move(task, "failed")
        return {"id": task.id, "state": task.state, "result": task.result if task.state == "completed" else ""}

    def get_task(self, peer: str, task_id: str) -> dict:
        task = self.tasks.get(task_id)
        if task is None or task.owner != peer:  # a peer can only see its own tasks
            return {"error": "not found"}
        return {"id": task.id, "state": task.state, "result": task.result}

    def cancel(self, peer: str, task_id: str) -> dict:
        task = self.tasks.get(task_id)
        if task is None or task.owner != peer:
            return {"error": "not found"}
        try:
            self._move(task, "canceled")
        except ValueError:
            return {"error": "not cancelable", "state": task.state}
        return {"id": task.id, "state": task.state}


def choose_route(cards: dict[str, AgentCard | None], origin: str, skill: str) -> dict:
    """Agent-to-agent only when the site publishes a card offering the skill; otherwise an explicitly labelled browser-automation fallback."""
    card = cards.get(origin)
    if card is not None and skill in card.skills:
        return {"mode": "agent-to-agent", "origin": origin, "skill": skill}
    return {"mode": "browser-automation", "origin": origin, "reason": "no card" if card is None else "skill not offered"}
