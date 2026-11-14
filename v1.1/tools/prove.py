#!/usr/bin/env python3
"""Proof-of-existence manifest: SHA-256 of files, never their content.

  python3 prove.py --repo ~/Personal/lucifer-lab --rev fe08665 [--file path ...] --out manifest.json
  python3 prove.py --verify manifest.json --repo ~/Personal/lucifer-lab

A manifest says: "these exact bytes existed when this manifest's root hash was anchored". The `created_at_claimed` field is the
author's clock and proves nothing; only an external anchor (OpenTimestamps, a signed tag pushed to a host, a notary) proves a date.
Repo files are hashed from git objects at --rev, so the working tree cannot change the result. Extra --file paths are hashed from disk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "lucifer-proof/1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def build(repo: Path, rev: str, extra: list[Path]) -> dict:
    commit = git(repo, "rev-parse", f"{rev}^{{commit}}").decode().strip()
    tree = git(repo, "rev-parse", f"{commit}^{{tree}}").decode().strip()
    entries = {}
    for line in git(repo, "ls-tree", "-r", "-z", commit).decode().split("\0"):
        if not line:
            continue
        meta, path = line.split("\t", 1)
        entries[path] = sha256(git(repo, "cat-file", "blob", meta.split()[2]))
    files = {p: {"sha256": h} for p, h in sorted(entries.items())}
    for f in extra:
        files[f"extra:{f.name}"] = {"sha256": sha256(f.read_bytes()), "bytes": f.stat().st_size}
    body = {
        "schema": SCHEMA,
        "repo_commit_sha1": commit,
        "repo_tree_sha1": tree,
        "file_count": len(files),
        "files": files,
        "created_at_claimed": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return {**body, "root_sha256": sha256(canonical(body))}


def verify(manifest: dict, repo: Path) -> bool:
    body = {k: v for k, v in manifest.items() if k != "root_sha256"}
    ok = sha256(canonical(body)) == manifest["root_sha256"]
    print(f"root hash matches manifest body: {ok}")
    commit = manifest["repo_commit_sha1"]
    bad = 0
    for path, info in manifest["files"].items():
        if path.startswith("extra:"):
            continue
        actual = sha256(git(repo, "cat-file", "blob", f"{commit}:{path}"))
        if actual != info["sha256"]:
            bad += 1
            print("MISMATCH", path)
    print(f"repo files checked: {len([p for p in manifest['files'] if not p.startswith('extra:')])}, mismatches: {bad}")
    return ok and bad == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path)
    ap.add_argument("--rev", default="HEAD")
    ap.add_argument("--file", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--verify", type=Path)
    a = ap.parse_args()
    if a.verify:
        return 0 if verify(json.loads(a.verify.read_text()), a.repo) else 1
    if not (a.repo and a.out):
        ap.error("--repo and --out are required")
    m = build(a.repo, a.rev, a.file)
    a.out.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    print(f"files: {m['file_count']}\ncommit: {m['repo_commit_sha1']}\nroot_sha256: {m['root_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
