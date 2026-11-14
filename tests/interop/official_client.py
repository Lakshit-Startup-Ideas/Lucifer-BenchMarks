"""Run with the isolated interop venv (it has the official `mcp` SDK; the main venv does not):
    .venv-interop/bin/python tests/interop/official_client.py <server-python> <repo-src-dir> <agent> <mode>
Starts our MCP server over stdio and drives it with the official client. Prints one JSON object describing what happened."""
import asyncio
import json
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def main(server_python: str, src: str, agent: str, mode: str) -> dict:
    out: dict = {"mode": mode, "agent": agent}
    params = StdioServerParameters(command=server_python, args=["-m", "lucv11.mcp_server", "--agent", agent], env={"PYTHONPATH": src})
    try:
        async with Client(params, mode=mode) as client:
            out["negotiated"] = str(getattr(client, "protocol_version", None) or getattr(getattr(client, "session", None), "protocol_version", None))
            tools = await client.list_tools()
            out["tools"] = sorted(t.name for t in tools.tools)
            out["schema_keys"] = sorted(tools.tools[0].input_schema.keys()) if hasattr(tools.tools[0], "input_schema") else sorted(vars(tools.tools[0]))
            ok = await client.call_tool("add", {"a": 2, "b": 3})
            out["add"] = {"text": ok.content[0].text, "is_error": ok.is_error}
            bad_input = await client.call_tool("add", {"a": "two", "b": 3})
            out["invalid"] = {"text": bad_input.content[0].text, "is_error": bad_input.is_error}
            denied = await client.call_tool("draft_email", {"to": "a@b.co", "body": "x"})
            out["external_without_approval"] = {"text": denied.content[0].text, "is_error": denied.is_error}
            missing = await client.call_tool("no_such_tool", {})
            out["unknown_tool"] = {"text": missing.content[0].text, "is_error": missing.is_error}
        out["ok"] = True
    except BaseException as exc:  # record exactly what happened, including the failure case
        out["ok"] = False
        out["exception"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return out


if __name__ == "__main__":
    print(json.dumps(asyncio.run(main(*sys.argv[1:5]))))
