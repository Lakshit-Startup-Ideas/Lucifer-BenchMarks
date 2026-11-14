"""Handshake-era MCP server (tools only) over JSON-RPC 2.0 on stdio, on top of ToolEngine. Registered in docs/M7-PREREGISTRATION.md.
Implements: initialize, notifications/initialized, ping, tools/list, tools/call. `server/discover` answers "method not found" on purpose, so a client in
auto mode falls back to the initialize handshake. NOT implemented: the 2026-07-28 revision, Streamable HTTP, resources, prompts, sampling, OAuth.
The connection runs as one configured agent identity (stdio has no in-band authentication)."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .tools import CallResult, Tool, ToolEngine

SUPPORTED_VERSIONS = ("2025-11-25", "2025-06-18")
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602
BEFORE_INIT = {"initialize", "ping", "server/discover"}


def _error(rid: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


class McpServer:
    def __init__(self, engine: ToolEngine, agent_id: str, name: str = "lucifer-tools", version: str = "0.0.1") -> None:
        self.engine, self.agent_id, self.info = engine, agent_id, {"name": name, "version": version}
        self.initialized = False

    def handle(self, msg: Any) -> dict | None:
        """One decoded JSON-RPC message in, one response out (None for notifications)."""
        if isinstance(msg, list):
            return _error(None, INVALID_REQUEST, "batch requests are not supported")
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            return _error(msg.get("id") if isinstance(msg, dict) and isinstance(msg.get("id"), (str, int)) else None, INVALID_REQUEST, "invalid request")
        method, rid, params = msg["method"], msg.get("id"), msg.get("params", {})
        if "id" not in msg:  # notification: never answered
            if method == "notifications/initialized":
                self.initialized = True
            return None
        if not isinstance(rid, (str, int)) or isinstance(rid, bool):
            return _error(None, INVALID_REQUEST, "invalid id")
        if not isinstance(params, dict):
            return _error(rid, INVALID_PARAMS, "params must be an object")
        if method not in BEFORE_INIT and not self.initialized:
            return _error(rid, INVALID_REQUEST, "server not initialized")
        if method == "initialize":
            requested = params.get("protocolVersion")
            if not isinstance(requested, str):
                return _error(rid, INVALID_PARAMS, "protocolVersion required")
            version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
            return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": version, "capabilities": {"tools": {"listChanged": False}}, "serverInfo": self.info}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": rid, "result": {}}
        if method == "tools/list":
            tools = [{"name": t.name, "description": t.description, "inputSchema": t.input_schema} for t in self.engine.list_tools(self.agent_id)]
            return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}}
        if method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments", {})
            if not isinstance(name, str):
                return _error(rid, INVALID_PARAMS, "tool name required")
            result: CallResult = self.engine.call(self.agent_id, name, arguments, approval=(params.get("_meta") or {}).get("approval") if isinstance(params.get("_meta"), dict) else None)
            text = result.text if result.ok else f"{result.code}: {result.error}"
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": text}], "isError": not result.ok}}
        return _error(rid, METHOD_NOT_FOUND, f"method not found: {method}")

    def serve(self, stdin=sys.stdin, stdout=sys.stdout) -> None:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                response = _error(None, PARSE_ERROR, "parse error")
            else:
                response = self.handle(msg)
            if response is not None:
                stdout.write(json.dumps(response) + "\n")
                stdout.flush()


def build_demo_engine() -> ToolEngine:
    engine = ToolEngine()
    engine.register_tool(Tool("echo", "Return the text unchanged.", {"type": "object", "properties": {"text": {"type": "string", "maxLength": 200}},
                                                                   "required": ["text"], "additionalProperties": False}, lambda a: a["text"], "read"))
    engine.register_tool(Tool("add", "Add two integers.", {"type": "object", "properties": {"a": {"type": "integer", "minimum": -10**6, "maximum": 10**6},
                                                                                         "b": {"type": "integer", "minimum": -10**6, "maximum": 10**6}},
                                                           "required": ["a", "b"], "additionalProperties": False}, lambda a: str(a["a"] + a["b"]), "read"))
    engine.register_tool(Tool("draft_email", "Prepare an email draft (external side effect: needs a one-time approval).",
                              {"type": "object", "properties": {"to": {"type": "string", "pattern": r"[^@\s]+@[^@\s]+\.[a-z]{2,}"}, "body": {"type": "string", "maxLength": 500}},
                               "required": ["to", "body"], "additionalProperties": False}, lambda a: f"draft prepared for {a['to']}", "external", external=True))
    engine.register_agent("reader", {"read"})
    engine.register_agent("writer", {"read", "external"})
    return engine


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="reader")
    args = parser.parse_args()
    McpServer(build_demo_engine(), args.agent).serve()
