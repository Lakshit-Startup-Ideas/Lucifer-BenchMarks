import time

import pytest

from lucv11.tools import MAX_OUTPUT_BYTES, Tool, ToolEngine, args_hash, validate

SCHEMA = {"type": "object", "properties": {"text": {"type": "string", "maxLength": 10, "pattern": "[a-z ]+"}, "n": {"type": "integer", "minimum": 0, "maximum": 5},
                                           "mode": {"enum": ["a", "b"]}, "tags": {"type": "array", "maxItems": 2, "items": {"type": "string"}},
                                           "nested": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"], "additionalProperties": False}},
          "required": ["text"], "additionalProperties": False}


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


@pytest.fixture
def env():
    clock, calls = Clock(), []
    engine = ToolEngine(clock=clock, rate_limit=3, rate_window_s=60, approval_ttl_s=100)
    def echo(a): calls.append(a); return a["text"]
    def circular(a): d = {}; d["self"] = d; return d
    engine.register_tool(Tool("echo", "echo", SCHEMA, echo, "read"))
    engine.register_tool(Tool("boom", "raises", {"type": "object"}, lambda a: (_ for _ in ()).throw(RuntimeError("PRIVATE-DETAIL")), "read"))
    engine.register_tool(Tool("huge", "big", {"type": "object"}, lambda a: "x" * (MAX_OUTPUT_BYTES + 1), "read"))
    engine.register_tool(Tool("circular", "cyc", {"type": "object"}, circular, "read"))
    engine.register_tool(Tool("slow", "slow", {"type": "object"}, lambda a: time.sleep(0.4) or "late", "read", timeout_s=0.05))
    engine.register_tool(Tool("send", "external", {"type": "object", "properties": {"to": {"type": "string"}}, "required": ["to"]}, lambda a: "sent", "external", external=True))
    engine.register_agent("r", {"read"})
    engine.register_agent("w", {"read", "external"})
    return engine, clock, calls


def test_default_deny_and_indistinguishable_refusals(env):
    engine, clock, calls = env
    assert engine.call("nobody", "echo", {"text": "hi"}).code == "unauthenticated"
    unknown, forbidden = engine.call("r", "no_such_tool", {}), engine.call("r", "send", {"to": "x"})
    assert (unknown.code, unknown.error) == (forbidden.code, forbidden.error) == ("forbidden", "tool unavailable")
    engine.revoke_agent("r")
    assert engine.call("r", "echo", {"text": "hi"}).code == "unauthenticated" and engine.list_tools("r") == []
    assert calls == []


def test_wildcard_capabilities_and_bad_tools_are_refused_at_registration(env):
    engine, *_ = env
    with pytest.raises(ValueError):
        engine.register_agent("x", {"*"})
    with pytest.raises(ValueError):
        engine.register_tool(Tool("echo", "dup", {"type": "object"}, lambda a: "", "read"))
    with pytest.raises(ValueError):
        engine.register_tool(Tool("bad name!", "x", {"type": "object"}, lambda a: "", "read"))
    with pytest.raises(ValueError):
        engine.register_tool(Tool("notobj", "x", {"type": "string"}, lambda a: "", "read"))


def test_discovery_is_filtered_by_capability(env):
    engine, *_ = env
    assert "send" not in {t.name for t in engine.list_tools("r")} and "send" in {t.name for t in engine.list_tools("w")}
    assert engine.list_tools("nobody") == []


@pytest.mark.parametrize("args", [
    {}, {"text": 5}, {"text": "UPPER"}, {"text": "waytoolongtext"}, {"text": "ok", "n": True}, {"text": "ok", "n": 9}, {"text": "ok", "n": -1}, {"text": "ok", "n": 1.5},
    {"text": "ok", "mode": "c"}, {"text": "ok", "extra": 1}, {"text": "ok", "tags": ["a", "b", "c"]}, {"text": "ok", "tags": [1]},
    {"text": "ok", "nested": {}}, {"text": "ok", "nested": {"x": "no"}}, {"text": "ok", "nested": {"x": 1, "y": 2}}])
def test_invalid_input_is_refused_before_the_handler_runs(env, args):
    engine, clock, calls = env
    assert engine.call("r", "echo", args).code == "invalid_input" and calls == []


def test_non_object_arguments_are_refused(env):
    engine, *_ = env
    assert engine.call("r", "echo", "text").code == "invalid_input" and engine.call("r", "echo", None).code == "invalid_input"


def test_valid_call_succeeds_and_validate_helper_handles_nan(env):
    engine, clock, calls = env
    assert engine.call("r", "echo", {"text": "hi there", "n": 3, "mode": "a", "tags": ["x"], "nested": {"x": 1}}).text == "hi there"
    assert validate({"type": "number"}, float("nan")) and validate({"type": "number"}, float("inf")) and not validate({"type": "number"}, 2.5)


def test_bad_outputs_and_handler_errors_become_error_results_without_leaking(env):
    engine, clock, _ = env
    assert engine.call("r", "huge", {}).code == "bad_output"
    assert engine.call("r", "circular", {}).code == "bad_output"
    boom = engine.call("r", "boom", {})
    assert boom.code == "handler_error" and "PRIVATE-DETAIL" not in boom.error
    assert "PRIVATE-DETAIL" not in " ".join(e.text for e in engine.ledger.entries)
    clock.t += 61  # the three calls above used the whole rate-limit window
    assert engine.call("r", "echo", {"text": "alive"}).ok


def test_timeout(env):
    engine, *_ = env
    assert engine.call("r", "slow", {}).code == "timeout"


def test_audit_covers_every_attempt_and_never_stores_raw_arguments(env):
    engine, *_ = env
    engine.call("r", "echo", {"text": "private canary"})
    engine.call("r", "echo", {"text": 5})
    engine.call("r", "send", {"to": "x"})
    engine.call("nobody", "echo", {"text": "private canary"})
    assert len(engine.ledger.entries) == 4 and engine.ledger.verify()
    blob = " ".join(e.text for e in engine.ledger.entries)
    assert "private canary" not in blob and args_hash({"text": "private canary"}) in blob
    import dataclasses
    engine.ledger.entries[1] = dataclasses.replace(engine.ledger.entries[1], text="{}")
    assert not engine.ledger.verify()


def test_rate_limit_applies_per_window(env):
    engine, clock, _ = env
    assert all(engine.call("r", "echo", {"text": "a"}).ok for _ in range(3))
    assert engine.call("r", "echo", {"text": "a"}).code == "rate_limited"
    clock.t += 61
    assert engine.call("r", "echo", {"text": "a"}).ok


def test_approval_is_one_time_bound_to_exact_arguments_agent_and_expiry(env):
    engine, clock, _ = env
    assert engine.call("w", "send", {"to": "a@b.co"}).code == "approval_required"
    token = engine.approve("w", "send", {"to": "a@b.co"})
    assert engine.call("w", "send", {"to": "a@b.co"}, approval=token).ok
    assert engine.call("w", "send", {"to": "a@b.co"}, approval=token).code == "approval_required"  # reuse
    other = engine.approve("w", "send", {"to": "a@b.co"})
    assert engine.call("w", "send", {"to": "evil@x.co"}, approval=other).code == "approval_required"  # different arguments
    assert engine.call("w", "send", {"to": "a@b.co"}, approval=other).code == "approval_required"  # and the token is burned
    stale = engine.approve("w", "send", {"to": "a@b.co"})
    clock.t += 101
    assert engine.call("w", "send", {"to": "a@b.co"}, approval=stale).code == "approval_required"  # expired
    engine.register_agent("w2", {"external"})
    mine = engine.approve("w", "send", {"to": "a@b.co"})
    assert engine.call("w2", "send", {"to": "a@b.co"}, approval=mine).code == "approval_required"  # another agent
