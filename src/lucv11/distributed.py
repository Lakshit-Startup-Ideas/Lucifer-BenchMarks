"""M5 prototype: a parent coordinator and independent children, in one process. Threat model and limits: docs/M5-THREAT-MODEL.md.
The parent sees metadata only (ledger head/length, parameter hashes, checkpoint names, evaluation numbers). Raw experiences and parameters stay in the child.
Secrets are random bytes held in memory and never written or printed."""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import secrets
from dataclasses import asdict, dataclass, field

import numpy as np

from .events import EventSourcedLearner
from .ledger import Ledger

HASH = re.compile(r"[0-9a-f]{64}")
NAME = re.compile(r"[a-z0-9_-]{1,32}")
MAX_PAYLOAD_BYTES = 2048
MAX_EVALUATIONS = 1000


def _hash(v) -> bool:
    return isinstance(v, str) and HASH.fullmatch(v) is not None


def _name(v) -> bool:
    return isinstance(v, str) and NAME.fullmatch(v) is not None


def _count(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 10**9


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and abs(v) <= 1e9


SCHEMAS = {
    "heartbeat": {"ledger_head": _hash, "ledger_length": _count, "params_sha256": _hash},
    "checkpoint": {"name": _name, "params_sha256": _hash, "ledger_head": _hash, "ledger_length": _count},
    "evaluation": {"suite": _name, "metric": _name, "value": _number, "n": _count},
}


def _mac(key: bytes, child_id: str, seq: int, kind: str, payload: dict) -> str:
    body = json.dumps({"child_id": child_id, "seq": seq, "type": kind, "payload": payload}, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(key, body, hashlib.sha256).hexdigest()


@dataclass
class ChildRecord:
    tenant: str
    active: bool = True
    last_seq: int = 0
    anchor_head: str = "0" * 64
    anchor_length: int = 0
    checkpoints: dict = field(default_factory=dict)
    checkpoint_anchors: dict = field(default_factory=dict)  # name -> (ledger head, ledger length) at the time of the checkpoint report
    evaluations: list = field(default_factory=list)


class Parent:
    def __init__(self) -> None:
        self.registry: dict[str, ChildRecord] = {}
        self.ledger = Ledger()  # the parent's own audit chain
        self._keys: dict[str, bytes] = {}
        self._n = 0

    def _audit(self, ident: str, kind: str, body: dict) -> None:
        self.ledger.add(ident, kind, json.dumps(body, sort_keys=True), "parent", 0)

    def issue_credentials(self, tenant: str) -> tuple[str, bytes]:
        if not _name(tenant):
            raise ValueError("tenant must be a short identifier")
        self._n += 1
        child_id = f"child-{self._n}"
        key = secrets.token_bytes(32)
        self._keys[child_id], self.registry[child_id] = key, ChildRecord(tenant)
        self._audit(child_id, "registration", {"tenant": tenant})
        return child_id, key

    def revoke(self, child_id: str) -> None:
        self.registry[child_id].active = False
        self._audit(child_id, "revocation", {})

    def _reject(self, claimed, reason: str) -> tuple[bool, str]:
        ident = re.sub(r"[^a-z0-9-]", "", str(claimed).lower())[:32] or "unknown"
        self._audit(ident, "rejection", {"reason": reason})  # never the payload
        return False, reason

    def receive(self, env: dict) -> tuple[bool, str]:
        if not isinstance(env, dict) or set(env) != {"child_id", "seq", "type", "payload", "mac"}:
            return self._reject(env.get("child_id") if isinstance(env, dict) else None, "malformed envelope")
        cid, seq, kind, payload, mac = env["child_id"], env["seq"], env["type"], env["payload"], env["mac"]
        rec = self.registry.get(cid) if isinstance(cid, str) else None
        if rec is None:
            return self._reject(cid, "unknown child")
        if not rec.active:
            return self._reject(cid, "revoked child")
        if not isinstance(seq, int) or isinstance(seq, bool) or not isinstance(kind, str) or not isinstance(payload, dict) or not isinstance(mac, str):
            return self._reject(cid, "malformed envelope")
        try:
            if len(json.dumps(payload)) > MAX_PAYLOAD_BYTES:
                return self._reject(cid, "payload too large")
            mac_ok = hmac.compare_digest(_mac(self._keys[cid], cid, seq, kind, payload), mac)
        except (TypeError, ValueError, OverflowError):  # not JSON-serialisable, circular, or otherwise hostile
            return self._reject(cid, "malformed envelope")
        if not mac_ok:
            return self._reject(cid, "bad mac")
        if seq <= rec.last_seq:
            return self._reject(cid, "replayed or out-of-order sequence")
        schema = SCHEMAS.get(kind)
        if schema is None:
            return self._reject(cid, "unknown message type")
        if set(payload) != set(schema) or not all(check(payload[k]) for k, check in schema.items()):
            return self._reject(cid, "payload violates schema")
        if kind in ("heartbeat", "checkpoint"):
            if payload["ledger_length"] < rec.anchor_length:
                return self._reject(cid, "anchor regression")
            if payload["ledger_length"] == rec.anchor_length and payload["ledger_head"] != rec.anchor_head:
                return self._reject(cid, "anchor fork")
            rec.anchor_head, rec.anchor_length = payload["ledger_head"], payload["ledger_length"]
        if kind == "checkpoint":
            rec.checkpoints[payload["name"]] = payload["params_sha256"]
            rec.checkpoint_anchors[payload["name"]] = (payload["ledger_head"], payload["ledger_length"])
        if kind == "evaluation" and len(rec.evaluations) < MAX_EVALUATIONS:
            rec.evaluations.append(dict(payload))
        rec.last_seq = seq
        self._audit(cid, kind, payload)
        return True, "ok"

    def verify_child(self, child: "Child") -> bool:
        rec = self.registry[child.child_id]
        return child.learner.ledger.verify_prefix(rec.anchor_head, rec.anchor_length)

    def export_state(self) -> str:
        """Everything the parent holds, as text (secrets excluded). Used to check that no raw data is present."""
        return json.dumps({"registry": {k: asdict(v) for k, v in self.registry.items()}, "ledger": [asdict(e) for e in self.ledger.entries]}, sort_keys=True)


class Child:
    def __init__(self, child_id: str, tenant: str, key: bytes, seed: int) -> None:
        self.child_id, self.tenant, self._key, self._seq = child_id, tenant, key, 0
        self.learner = EventSourcedLearner(seed, run_id=child_id)
        self._checkpoint_anchor: dict[str, tuple[str, int]] = {}

    def envelope(self, kind: str, payload: dict) -> dict:
        self._seq += 1
        return {"child_id": self.child_id, "seq": self._seq, "type": kind, "payload": payload, "mac": _mac(self._key, self.child_id, self._seq, kind, payload)}

    def _anchor(self) -> dict:
        return {"ledger_head": self.learner.ledger.head, "ledger_length": len(self.learner.ledger.entries)}

    def heartbeat(self) -> dict:
        return self.envelope("heartbeat", {**self._anchor(), "params_sha256": self.learner.model.params_hash()})

    def checkpoint(self, name: str) -> dict:
        self.learner.checkpoint(name)
        self._checkpoint_anchor[name] = (self.learner.ledger.head, len(self.learner.ledger.entries))
        return self.envelope("checkpoint", {"name": name, "params_sha256": self.learner.checkpoints[name].params_hash(), **self._anchor()})

    def evaluation(self, suite: str, metric: str, value: float, n: int) -> dict:
        return self.envelope("evaluation", {"suite": suite, "metric": metric, "value": float(value), "n": n})

    def restore(self, name: str, parent_hash: str) -> bool:
        """Restore a local checkpoint only if it matches the hash the parent recorded."""
        saved = self.learner.checkpoints.get(name)
        if saved is None or saved.params_hash() != parent_hash:
            return False
        self.learner.model = saved.copy()
        return True

    def observe_and_learn(self, ctx: int, x: np.ndarray, y: int, lr: float = 0.1) -> None:
        self.learner.learn([self.learner.observe(ctx, x, y)], lr=lr)

    def export_package(self, ctx: int, checkpoint_name: str, consent: bool = True, rule: np.ndarray | None = None) -> dict:
        """A knowledge package: the decision rule this child learned for one context, unit length, plus provenance. `rule` overrides the
        derived rule (an attacker is free to do this; the parent cannot tell from metadata alone)."""
        if rule is None:
            model = self.learner.checkpoints[checkpoint_name]
            rule = model.U @ model.head(ctx)
            rule = rule / (np.linalg.norm(rule) or 1.0)
        head, length = self._checkpoint_anchor[checkpoint_name]
        return {"origin": self.child_id, "ctx": ctx, "rule": [float(v) for v in rule], "checkpoint": checkpoint_name,
                "params_sha256": self.learner.checkpoints[checkpoint_name].params_hash(), "ledger_head": head, "ledger_length": length, "consent": consent}
