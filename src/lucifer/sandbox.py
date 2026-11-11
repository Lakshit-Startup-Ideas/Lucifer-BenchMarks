"""Runs model-written code against a task's hidden tests in a separate Python process.

This limits CPU time and file size and runs in a throwaway folder with an empty environment. It is NOT a security boundary: the code
can still reach the network and the user's files. The V1 tasks are tiny, but anything untrusted at scale must run in a container or on
a cloud runner.
"""
from __future__ import annotations

import json
import re
import resource
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .tasks import Task

_RUNNER = """
import json, sys
src = open("cand.py").read()
tests = json.load(open("tests.json"))
ns = {}
try:
    exec(compile(src, "candidate", "exec"), ns)
except BaseException as e:
    print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"})); sys.exit(0)
for t in tests:
    try:
        exec(t, ns)
    except BaseException as e:
        print(json.dumps({"ok": False, "error": f"this check failed: {t}  ({type(e).__name__}: {e})"})); sys.exit(0)
print(json.dumps({"ok": True}))
"""

_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(reply: str) -> str:
    """The first fenced code block, or the whole reply if there is none."""
    match = _FENCE.search(reply)
    return (match.group(1) if match else reply).strip("\n")


@dataclass(frozen=True)
class ExecResult:
    passed: bool
    feedback: str  # what the model is told after a failure
    ms: float


class Executor(Protocol):
    def run(self, task: Task, code: str) -> ExecResult: ...


def _limits() -> None:  # runs in the child process before it starts
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1_000_000, 1_000_000))


class SandboxExecutor:
    def __init__(self, timeout_s: float = 8.0) -> None:
        self.timeout_s = timeout_s

    def run(self, task: Task, code: str) -> ExecResult:
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="lucifer-") as folder:
            root = Path(folder)
            (root / "cand.py").write_text(code)
            (root / "tests.json").write_text(json.dumps(list(task.tests)))
            (root / "run.py").write_text(_RUNNER)
            try:
                done = subprocess.run(
                    [sys.executable, "-I", "run.py"], cwd=root, env={}, capture_output=True, text=True,
                    timeout=self.timeout_s, preexec_fn=_limits,
                )
                lines = done.stdout.strip().splitlines()
                outcome = json.loads(lines[-1]) if lines else {"ok": False, "error": (done.stderr or "no output")[-300:]}
            except subprocess.TimeoutExpired:
                outcome = {"ok": False, "error": f"the code did not finish within {self.timeout_s:.0f} seconds"}
            except json.JSONDecodeError:
                outcome = {"ok": False, "error": "the code produced unreadable output"}
        ms = (time.perf_counter() - started) * 1000
        return ExecResult(bool(outcome["ok"]), "" if outcome["ok"] else str(outcome["error"])[:400], ms)


class FastExecutor:
    """For simulated agents only: a candidate passes exactly when it is the reference solution. Never used with real models."""

    def run(self, task: Task, code: str) -> ExecResult:
        ok = code.strip() == task.reference.strip()
        return ExecResult(ok, "" if ok else f"this check failed: {task.tests[0]}", 0.0)
