"""Interoperability with the OFFICIAL MCP Python SDK (mcp 2.3.0), installed only in the isolated .venv-interop. Skipped when that venv is absent."""
import json
import os
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INTEROP_PY = os.path.join(ROOT, ".venv-interop", "bin", "python")
pytestmark = pytest.mark.skipif(not os.path.exists(INTEROP_PY), reason="isolated interop venv with the official mcp SDK not installed")


def run(agent: str, mode: str) -> dict:
    out = subprocess.run([INTEROP_PY, os.path.join(ROOT, "tests", "interop", "official_client.py"), os.path.join(ROOT, ".venv", "bin", "python"), os.path.join(ROOT, "src"), agent, mode],
                         capture_output=True, text=True, timeout=120, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_official_client_lists_calls_and_receives_tool_errors_without_raising(mode):
    r = run("reader", mode)
    assert r["ok"], r.get("exception")
    assert r["tools"] == ["add", "echo"]  # exactly what the reader may call
    assert r["add"] == {"text": "5", "is_error": False}
    assert r["invalid"]["is_error"] is True and r["external_without_approval"]["is_error"] is True and r["unknown_tool"]["is_error"] is True
    assert r["external_without_approval"]["text"] == r["unknown_tool"]["text"]  # a hidden tool is indistinguishable from a missing one


def test_official_client_sees_the_extra_tool_for_the_writer_agent():
    r = run("writer", "legacy")
    assert r["ok"] and r["tools"] == ["add", "draft_email", "echo"]
    assert "approval_required" in r["external_without_approval"]["text"] and r["external_without_approval"]["is_error"] is True


def test_the_2026_07_28_revision_is_not_supported_and_not_claimed():
    r = run("reader", "2026-07-28")
    assert r["ok"] is False  # documents the limit; if a future change makes this pass, update the claims in M7-RESULTS.md
