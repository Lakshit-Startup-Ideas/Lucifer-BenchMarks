"""Append-only hash-chained ledger, scheme v2. Fixes three V1 weaknesses found on 14 Nov 2026 (see docs/V1-HASH-FINDINGS.md):
  1. V1 did not hash run_id / seed, so provenance could be edited without breaking the chain.      -> v2 hashes every field.
  2. V1 joined fields with "|" and no length, so ("a|b","c") and ("a","b|c") collided.             -> v2 length-prefixes every field.
  3. A chain alone cannot show that the whole history was rewritten.                              -> verify() can take an externally stored head.
`hash_v1` reproduces the V1 formula byte for byte so V1 data stays verifiable.
A hash chain detects edits when it is checked; it does not prevent them, and it says nothing about who made a change.
"""
from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

GENESIS = "0" * 64
DOMAIN = b"lucifer-ledger/2"


def hash_v1(parent: str, version: int, task_id: str, kind: str, text: str) -> str:
    return hashlib.sha256("|".join([parent, str(version), task_id, kind, text]).encode()).hexdigest()


def hash_v2(parent: str, version: int, task_id: str, kind: str, text: str, run_id: str, seed: int) -> str:
    h = hashlib.sha256(DOMAIN)
    for field in (parent, str(version), task_id, kind, text, run_id, str(seed)):
        raw = field.encode()
        h.update(struct.pack(">Q", len(raw)) + raw)
    return h.hexdigest()


@dataclass(frozen=True)
class Entry:
    version: int
    task_id: str
    kind: str
    text: str
    run_id: str
    seed: int
    parent_hash: str
    hash: str


class Ledger:
    def __init__(self) -> None:
        self.entries: list[Entry] = []

    @property
    def head(self) -> str:
        return self.entries[-1].hash if self.entries else GENESIS

    def add(self, task_id: str, kind: str, text: str, run_id: str, seed: int) -> Entry:
        if not task_id or not run_id or seed < 0:
            raise ValueError("task_id, run_id and a non-negative seed are required")
        version = len(self.entries) + 1
        entry = Entry(version, task_id, kind, text, run_id, seed, self.head, hash_v2(self.head, version, task_id, kind, text, run_id, seed))
        self.entries.append(entry)
        return entry

    def verify(self, expected_head: str | None = None, expected_length: int | None = None) -> bool:
        """Checks every link. With expected_head / expected_length (stored somewhere the ledger's owner cannot edit) it also catches a
        truncated or fully rewritten history, which the links alone cannot."""
        parent = GENESIS
        for i, e in enumerate(self.entries, start=1):
            if e.version != i or e.parent_hash != parent or hash_v2(parent, e.version, e.task_id, e.kind, e.text, e.run_id, e.seed) != e.hash:
                return False
            parent = e.hash
        if expected_length is not None and len(self.entries) != expected_length:
            return False
        return expected_head is None or parent == expected_head

    def verify_prefix(self, anchor_head: str, anchor_length: int) -> bool:
        """The whole chain verifies AND its first `anchor_length` entries end at `anchor_head`. For an anchor stored earlier: the owner may have
        appended since, but must not have rewritten or truncated anything the anchor covers."""
        if not self.verify() or len(self.entries) < anchor_length:
            return False
        return (self.entries[anchor_length - 1].hash if anchor_length else GENESIS) == anchor_head
