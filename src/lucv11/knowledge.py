"""M6: knowledge packages, the versioned shared knowledge base, and the reviewer. Registered in docs/M6-PREREGISTRATION.md.
Peers report only two numbers per package (through the M5 evaluation message); their validation data never leaves them."""
from __future__ import annotations

import hashlib
import json
import math

import numpy as np

from .distributed import Child, Parent
from .learner import D
from .ledger import Ledger

PEER_MARGIN, CONFLICT_MARGIN, CONFLICT_COSINE = 0.05, 0.10, 0.3


def cosine(a, b) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float(a @ b / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1.0))


class KnowledgeBase:
    """Promotions and rollbacks are entries on a Ledger v2 chain; the active set is recomputed by replaying them. Nothing is ever deleted."""

    def __init__(self) -> None:
        self.ledger = Ledger()
        self._next_version = 1

    def promote(self, pkg: dict, evidence: dict) -> int:
        version = self._next_version
        self._next_version += 1
        self.ledger.add(f"v{version}", "promotion", json.dumps({"version": version, "package": pkg, "evidence": evidence}, sort_keys=True), "kb", 0)
        return version

    def rollback(self, to_version: int, reason: str) -> None:
        if not 0 <= to_version < self._next_version:
            raise ValueError("unknown version")
        self.ledger.add(f"rollback-to-v{to_version}", "rollback", json.dumps({"to_version": to_version, "reason": reason}, sort_keys=True), "kb", 0)

    def _replay(self) -> tuple[list[dict], list[dict]]:
        active: list[dict] = []
        archived: list[dict] = []
        for e in self.ledger.entries:
            body = json.loads(e.text)
            if e.kind == "promotion":
                active.append({"version": body["version"], **body["package"]})
            elif e.kind == "rollback":
                archived += [p for p in active if p["version"] > body["to_version"]]
                active = [p for p in active if p["version"] <= body["to_version"]]
        return active, archived

    def current(self) -> dict[int, dict]:
        """Latest active package per context."""
        return {p["ctx"]: p for p in self._replay()[0]}

    def archived(self) -> list[dict]:
        return self._replay()[1]

    def state_hash(self) -> str:
        h = hashlib.sha256()
        for ctx, p in sorted(self.current().items()):
            h.update(f"{ctx}|{p['pkg_id']}|{p['version']}|".encode() + np.asarray(p["rule"], dtype=np.float64).tobytes())
        return h.hexdigest()

    def verify(self) -> bool:
        return self.ledger.verify()


class Reviewer:
    def __init__(self, parent: Parent, kb: KnowledgeBase) -> None:
        self.parent, self.kb, self._n = parent, kb, 0

    def new_id(self) -> str:
        self._n += 1
        return f"pkg-{self._n}"

    def deterministic(self, pkg: dict, origin: Child) -> list[str]:
        """Metadata-only checks. An empty list means the package passed."""
        why = []
        rec = self.parent.registry.get(pkg.get("origin"))
        if rec is None or not rec.active:
            return ["origin unknown or revoked"]
        if pkg.get("consent") is not True:
            why.append("no consent")
        name = pkg.get("checkpoint")
        if name not in rec.checkpoints:
            why.append("checkpoint not recorded")
        else:
            if rec.checkpoints[name] != pkg.get("params_sha256"):
                why.append("checkpoint hash mismatch")
            if tuple(rec.checkpoint_anchors.get(name, ())) != (pkg.get("ledger_head"), pkg.get("ledger_length")):
                why.append("anchor mismatch")
        if not self.parent.verify_child(origin):
            why.append("origin history not verified")
        rule = pkg.get("rule")
        if not isinstance(rule, list) or len(rule) != D:
            why.append("rule invalid length")
        elif not all(isinstance(v, float) and math.isfinite(v) for v in rule):
            why.append("rule not finite")
        elif abs(float(np.linalg.norm(rule)) - 1.0) > 1e-6:
            why.append("rule norm")
        return why

    def peer_evidence(self, pkg: dict, peers: list) -> dict:
        """Each peer scores the package and its own local model on private data and sends two evaluation messages. Only those numbers are read."""
        evidence = {}
        for peer in peers:
            for env in peer.evaluate(pkg):
                ok, reason = self.parent.receive(env)
                if not ok:
                    raise RuntimeError(f"peer message rejected: {reason}")
            records = {r["metric"]: r["value"] for r in self.parent.registry[peer.child.child_id].evaluations if r["suite"] == pkg["pkg_id"]}
            evidence[peer.child.child_id] = {"pkg_acc": records["pkg-acc"], "local_acc": records["local-acc"]}
        return evidence

    def required_margin(self, pkg: dict) -> float:
        old = self.kb.current().get(pkg["ctx"])
        return CONFLICT_MARGIN if old is not None and cosine(old["rule"], pkg["rule"]) < CONFLICT_COSINE else PEER_MARGIN

    def peers_agree(self, pkg: dict, evidence: dict) -> bool:
        margin = self.required_margin(pkg)
        return bool(evidence) and all(v["pkg_acc"] - v["local_acc"] >= margin - 1e-12 for v in evidence.values())
