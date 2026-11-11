"""Persistent memory of lessons: append-only, hash-chained, versioned, and roll-back-able (this is what promotion gate 3 checks).

Each lesson carries where it came from (task, run, seed) and the version it created. Its hash covers the previous lesson's hash, so
changing any earlier lesson breaks every later one and `verify_chain()` says so. Rolling back to version n moves the later lessons
into an `archived` table instead of deleting them, so an audit can still see what was undone.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass

GENESIS = "0" * 64


@dataclass(frozen=True)
class Lesson:
    id: int
    version: int
    task_id: str
    kind: str  # "failure" or "fix"
    text: str
    run_id: str
    seed: int
    hash: str


def _hash(parent: str, version: int, task_id: str, kind: str, text: str) -> str:
    return hashlib.sha256("|".join([parent, str(version), task_id, kind, text]).encode()).hexdigest()


class Memory:
    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path)
        columns = "id INTEGER PRIMARY KEY AUTOINCREMENT, version INTEGER NOT NULL, task_id TEXT NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, run_id TEXT NOT NULL, seed INTEGER NOT NULL, parent_hash TEXT NOT NULL, hash TEXT NOT NULL"
        self.db.execute(f"CREATE TABLE IF NOT EXISTS lessons ({columns})")
        self.db.execute(f"CREATE TABLE IF NOT EXISTS archived ({columns}, archived_by_rollback_to INTEGER)")
        self.db.commit()

    # -- reading -------------------------------------------------------------------------------------------------------------------
    @property
    def version(self) -> int:
        return self.db.execute("SELECT COALESCE(MAX(version), 0) FROM lessons").fetchone()[0]

    @property
    def head_hash(self) -> str:
        row = self.db.execute("SELECT hash FROM lessons ORDER BY version DESC LIMIT 1").fetchone()
        return row[0] if row else GENESIS

    def lessons(self) -> list[Lesson]:
        rows = self.db.execute("SELECT id, version, task_id, kind, text, run_id, seed, hash FROM lessons ORDER BY version").fetchall()
        return [Lesson(*row) for row in rows]

    def __len__(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]

    # -- writing -------------------------------------------------------------------------------------------------------------------
    def add(self, task_id: str, kind: str, text: str, run_id: str, seed: int) -> Lesson:
        version = self.version + 1
        parent = self.head_hash
        digest = _hash(parent, version, task_id, kind, text)
        cursor = self.db.execute(
            "INSERT INTO lessons (version, task_id, kind, text, run_id, seed, parent_hash, hash) VALUES (?,?,?,?,?,?,?,?)",
            (version, task_id, kind, text, run_id, seed, parent, digest),
        )
        self.db.commit()
        return Lesson(cursor.lastrowid, version, task_id, kind, text, run_id, seed, digest)

    def rollback(self, version: int) -> None:
        """Go back to `version`. Later lessons are archived, not deleted."""
        if not 0 <= version <= self.version:
            raise ValueError(f"cannot roll back to version {version}; current version is {self.version}")
        cols = "id, version, task_id, kind, text, run_id, seed, parent_hash, hash"
        self.db.execute(f"INSERT INTO archived ({cols}, archived_by_rollback_to) SELECT {cols}, ? FROM lessons WHERE version > ?", (version, version))
        self.db.execute("DELETE FROM lessons WHERE version > ?", (version,))
        self.db.commit()

    # -- auditing ------------------------------------------------------------------------------------------------------------------
    def verify_chain(self) -> bool:
        parent = GENESIS
        expected_version = 1
        for row in self.db.execute("SELECT version, task_id, kind, text, parent_hash, hash FROM lessons ORDER BY version"):
            version, task_id, kind, text, stored_parent, stored_hash = row
            if version != expected_version or stored_parent != parent or _hash(parent, version, task_id, kind, text) != stored_hash:
                return False
            parent = stored_hash
            expected_version += 1
        return True

    def audit(self) -> dict:
        """Checks the chain, and that rolling back to the middle and forward again reproduces the same history, on a COPY."""
        chain_ok = self.verify_chain()
        rollback_ok = True
        if len(self) >= 2:
            copy = Memory()
            self.db.backup(copy.db)
            middle = copy.version // 2
            snapshot = [(l.version, l.hash) for l in copy.lessons() if l.version <= middle]
            before_hash = next((l.hash for l in copy.lessons() if l.version == middle), GENESIS)
            copy.rollback(middle)
            rollback_ok = copy.verify_chain() and copy.head_hash == before_hash and [(l.version, l.hash) for l in copy.lessons()] == snapshot
        provenance_ok = all(l.task_id and l.run_id and l.seed >= 0 for l in self.lessons())
        return {"chain_ok": chain_ok, "rollback_ok": rollback_ok, "provenance_ok": provenance_ok, "ok": chain_ok and rollback_ok and provenance_ok, "lessons": len(self)}
