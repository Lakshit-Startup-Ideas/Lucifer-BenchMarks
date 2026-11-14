import io
import json
import os
import subprocess
import sys

import pytest

from lucv11.mcp_server import McpServer, build_demo_engine


def server(agent="reader", init=True):
    s = McpServer(build_demo_engine(), agent)
    if init:
        s.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return s


def rpc(s, method, params=None, rid=1):
    msg = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        msg["params"] = params
    return s.handle(msg)


def test_initialize_negotiates_a_supported_version_and_declares_tools():
    s = server(init=False)
    r = rpc(s, "initialize", {"protocolVersion": "2025-06-18"})["result"]
    assert r["protocolVersion"] == "2025-06-18" and r["capabilities"]["tools"] == {"listChanged": False} and r["serverInfo"]["name"]
    assert rpc(s, "initialize", {"protocolVersion": "1999-01-01"})["result"]["protocolVersion"] == "2025-11-25"
    assert rpc(s, "initialize", {})["error"]["code"] == -32602


def test_requests_before_initialization_are_refused_but_ping_works():
    s = server(init=False)
    assert rpc(s, "tools/list")["error"]["code"] == -32600
    assert rpc(s, "ping")["result"] == {}


def test_ids_are_echoed_and_notifications_get_no_reply():
    s = server()
    assert rpc(s, "ping", rid="abc")["id"] == "abc" and rpc(s, "ping", rid=7)["id"] == 7
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/anything"}) is None


@pytest.mark.parametrize("bad", [{"id": 1, "method": "ping"}, {"jsonrpc": "1.0", "id": 1, "method": "ping"}, {"jsonrpc": "2.0", "id": 1}, "text", 5, None,
                                 {"jsonrpc": "2.0", "id": True, "method": "ping"}, {"jsonrpc": "2.0", "id": [1], "method": "ping"}])
def test_invalid_requests_get_invalid_request_errors(bad):
    assert server().handle(bad)["error"]["code"] == -32600


def test_batches_unknown_methods_discover_and_bad_params():
    s = server()
    assert s.handle([{"jsonrpc": "2.0", "id": 1, "method": "ping"}])["error"]["code"] == -32600
    assert rpc(s, "no/such")["error"]["code"] == -32601
    assert rpc(s, "server/discover")["error"]["code"] == -32601  # on purpose: lets an auto-mode client fall back
    assert s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": [1]})["error"]["code"] == -32602
    assert rpc(s, "tools/call", {"arguments": {}})["error"]["code"] == -32602


def test_tools_list_shape_and_per_agent_filtering():
    reader = rpc(server("reader"), "tools/list")["result"]["tools"]
    writer = rpc(server("writer"), "tools/list")["result"]["tools"]
    assert {t["name"] for t in reader} == {"echo", "add"} and "draft_email" in {t["name"] for t in writer}
    assert all(set(t) == {"name", "description", "inputSchema"} and t["inputSchema"]["type"] == "object" for t in reader + writer)


def test_tools_call_success_and_error_shapes():
    s = server()
    ok = rpc(s, "tools/call", {"name": "add", "arguments": {"a": 2, "b": 3}})["result"]
    assert ok == {"content": [{"type": "text", "text": "5"}], "isError": False}
    for params in ({"name": "add", "arguments": {"a": "x", "b": 3}}, {"name": "draft_email", "arguments": {"to": "a@b.co", "body": "x"}}, {"name": "nope", "arguments": {}}):
        r = rpc(s, "tools/call", params)["result"]
        assert r["isError"] is True and r["content"][0]["type"] == "text"  # tool errors are results, not protocol errors


def test_external_tool_needs_a_one_time_approval_passed_in_meta():
    engine = build_demo_engine()
    s = McpServer(engine, "writer")
    s.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}})
    s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    args = {"to": "a@b.co", "body": "hello"}
    assert rpc(s, "tools/call", {"name": "draft_email", "arguments": args})["result"]["isError"] is True
    token = engine.approve("writer", "draft_email", args)
    assert rpc(s, "tools/call", {"name": "draft_email", "arguments": args, "_meta": {"approval": token}})["result"]["isError"] is False
    assert rpc(s, "tools/call", {"name": "draft_email", "arguments": args, "_meta": {"approval": token}})["result"]["isError"] is True


def test_stdio_loop_handles_parse_errors_blank_lines_and_notifications():
    lines = ["", "{not json", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}),
             json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}), json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})]
    out = io.StringIO()
    server(init=False).serve(io.StringIO("\n".join(lines) + "\n"), out)
    replies = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [None, 1, 2] and replies[0]["error"]["code"] == -32700 and "tools" in replies[2]["result"]


def test_real_subprocess_speaks_json_rpc_over_stdio():
    src = os.path.join(os.path.dirname(__file__), "..", "src")
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}}, {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "echo", "arguments": {"text": "hello"}}}]
    proc = subprocess.run([sys.executable, "-m", "lucv11.mcp_server", "--agent", "reader"], input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": src}, timeout=30)
    replies = [json.loads(x) for x in proc.stdout.splitlines()]
    assert proc.returncode == 0 and replies[1]["result"]["content"][0]["text"] == "hello"
