"""M7 tool engine: registration, discovery, deny-by-default permissions, input/output validation, rate limit, timeout, one-time approvals, audit.
Independent of any wire protocol; the MCP adapter (mcp_server.py) is a thin layer on top. Registered in docs/M7-PREREGISTRATION.md.
Audit entries hold hashes and names, never raw arguments or outputs. A handler that times out keeps running in its thread (Python cannot kill it)."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from typing import Any, Callable

from .ledger import Ledger

MAX_OUTPUT_BYTES = 64 * 1024


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def args_hash(args: dict) -> str:
    return hashlib.sha256(canonical(args).encode()).hexdigest()


def validate(schema: dict, value: Any, path: str = "$") -> list[str]:
    """A small JSON-Schema subset: type, required, properties, additionalProperties, enum, minimum, maximum, minLength, maxLength, pattern, items, maxItems."""
    errors: list[str] = []
    t = schema.get("type")
    kinds = {"object": dict, "array": list, "string": str, "boolean": bool}
    if t in kinds:
        if not isinstance(value, kinds[t]):
            return [f"{path}: expected {t}"]
    elif t == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return [f"{path}: expected integer"]
    elif t == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value != value or value in (float("inf"), float("-inf")):
            return [f"{path}: expected finite number"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not in enum")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: too long")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            errors.append(f"{path}: pattern mismatch")
    if isinstance(value, list):
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: too many items")
        if "items" in schema:
            for i, item in enumerate(value):
                errors += validate(schema["items"], item, f"{path}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required")
        if schema.get("additionalProperties") is False:
            errors += [f"{path}.{k}: not allowed" for k in value if k not in props]
        for key, sub in props.items():
            if key in value:
                errors += validate(sub, value[key], f"{path}.{key}")
    return errors


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], Any]
    capability: str
    external: bool = False  # side effects outside the system: needs a one-time approval
    timeout_s: float = 5.0


@dataclass
class CallResult:
    ok: bool
    text: str = ""
    code: str = "ok"
    error: str = ""


@dataclass
class _Agent:
    capabilities: frozenset
    active: bool = True
    calls: list = field(default_factory=list)


class ToolEngine:
    def __init__(self, clock: Callable[[], float] = time.monotonic, rate_limit: int = 30, rate_window_s: float = 60.0, approval_ttl_s: float = 300.0) -> None:
        self.clock, self.rate_limit, self.rate_window_s, self.approval_ttl_s = clock, rate_limit, rate_window_s, approval_ttl_s
        self.tools: dict[str, Tool] = {}
        self.agents: dict[str, _Agent] = {}
        self.ledger = Ledger()
        self._approvals: dict[str, tuple[str, str, str, float]] = {}  # token hash -> (agent, tool, args hash, expiry)
        self._pool = ThreadPoolExecutor(max_workers=4)

    def register_tool(self, tool: Tool) -> None:
        if tool.name in self.tools or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", tool.name) or tool.input_schema.get("type") != "object":
            raise ValueError("invalid or duplicate tool")
        self.tools[tool.name] = tool

    def register_agent(self, agent_id: str, capabilities: set[str]) -> None:
        if "*" in capabilities:
            raise ValueError("wildcard capabilities are not allowed")
        self.agents[agent_id] = _Agent(frozenset(capabilities))

    def revoke_agent(self, agent_id: str) -> None:
        self.agents[agent_id].active = False

    def _audit(self, agent_id: str, tool: str, args: dict | None, decision: str, reason: str, started: float) -> None:
        body = {"agent": agent_id, "tool": tool, "decision": decision, "reason": reason, "ms": round((self.clock() - started) * 1000, 3)}
        if isinstance(args, dict):
            body.update({"args_sha256": args_hash(args), "arg_names": sorted(str(k) for k in args)})
        self.ledger.add(re.sub(r"[^a-zA-Z0-9_-]", "_", str(agent_id))[:64] or "unknown", "tool-call", canonical(body), "tool-engine", 0)

    def list_tools(self, agent_id: str) -> list[Tool]:
        agent = self.agents.get(agent_id)
        if agent is None or not agent.active:
            return []
        return [t for t in self.tools.values() if t.capability in agent.capabilities]

    def approve(self, agent_id: str, tool_name: str, args: dict) -> str:
        """A human step: mint a one-time approval for this agent, tool and these exact arguments."""
        token = secrets.token_hex(16)
        self._approvals[hashlib.sha256(token.encode()).hexdigest()] = (agent_id, tool_name, args_hash(args), self.clock() + self.approval_ttl_s)
        return token

    def _deny(self, agent_id, tool, args, code, reason, started) -> CallResult:
        self._audit(agent_id, tool, args, "denied", code, started)
        return CallResult(False, code=code, error=reason)

    def call(self, agent_id: str, tool_name: str, args: dict, approval: str | None = None) -> CallResult:
        started = self.clock()
        agent = self.agents.get(agent_id)
        if agent is None or not agent.active:
            return self._deny(agent_id, tool_name, args, "unauthenticated", "unknown or revoked agent", started)
        tool = self.tools.get(tool_name) if isinstance(tool_name, str) else None
        if tool is None or tool.capability not in agent.capabilities:
            return self._deny(agent_id, tool_name, args, "forbidden", "tool unavailable", started)  # same answer for unknown and not permitted
        if not isinstance(args, dict):
            return self._deny(agent_id, tool_name, None, "invalid_input", "arguments must be an object", started)
        errors = validate(tool.input_schema, args)
        if errors:
            return self._deny(agent_id, tool_name, args, "invalid_input", "; ".join(errors[:5]), started)
        agent.calls = [t for t in agent.calls if started - t < self.rate_window_s]
        if len(agent.calls) >= self.rate_limit:
            return self._deny(agent_id, tool_name, args, "rate_limited", "too many calls", started)
        if tool.external:
            record = self._approvals.pop(hashlib.sha256((approval or "").encode()).hexdigest(), None)  # popped: single use, even when refused
            if record is None or record[:3] != (agent_id, tool_name, args_hash(args)) or record[3] < started:
                return self._deny(agent_id, tool_name, args, "approval_required", "a valid one-time approval for these exact arguments is required", started)
        agent.calls.append(started)
        try:
            raw = self._pool.submit(tool.handler, args).result(timeout=tool.timeout_s)
        except FutureTimeout:
            return self._deny(agent_id, tool_name, args, "timeout", "tool timed out", started)
        except Exception as exc:  # a handler bug must not take the engine down; the message is not echoed (it may contain private data)
            return self._deny(agent_id, tool_name, args, "handler_error", type(exc).__name__, started)
        try:
            text = raw if isinstance(raw, str) else canonical(raw)
        except (TypeError, ValueError):
            return self._deny(agent_id, tool_name, args, "bad_output", "output not serialisable", started)
        if len(text.encode()) > MAX_OUTPUT_BYTES:
            return self._deny(agent_id, tool_name, args, "bad_output", "output too large", started)
        self._audit(agent_id, tool_name, args, "allowed", "ok", started)
        return CallResult(True, text=text)
