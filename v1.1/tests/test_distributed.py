import dataclasses
import json

import numpy as np
import pytest

from lucv11.distributed import Child, Parent
from lucv11.events import EventSourcedLearner, content_hash
from lucv11.learner import D
from lucv11.ledger import Ledger


@pytest.fixture
def net():
    parent = Parent()
    ca, ka = parent.issue_credentials("tenant-a")
    cb, kb = parent.issue_credentials("tenant-b")
    return parent, Child(ca, "tenant-a", ka, 1), Child(cb, "tenant-b", kb, 2)


def train(child, n=6, ctx=0, seed=0, canary=None):
    rng = np.random.default_rng(seed)
    for i in range(n):
        x = canary if (canary is not None and i == 0) else rng.normal(size=D)
        child.observe_and_learn(ctx, x, int(rng.integers(0, 2)))


# --- P1 registration -------------------------------------------------------------------------------------------------------------
def test_unregistered_and_revoked_children_are_rejected_without_logging_the_payload(net):
    parent, a, _ = net
    ok, _ = parent.receive(a.heartbeat())
    assert ok
    stranger = Child("child-99", "tenant-x", b"k" * 32, 0)
    env = stranger.envelope("heartbeat", {"ledger_head": "0" * 64, "ledger_length": 0, "params_sha256": "SECRET-CANARY-PAYLOAD"})
    assert parent.receive(env) == (False, "unknown child")
    parent.revoke(a.child_id)
    assert parent.receive(a.heartbeat()) == (False, "revoked child")
    assert "SECRET-CANARY-PAYLOAD" not in parent.export_state()


def test_tenant_must_be_a_short_identifier():
    with pytest.raises(ValueError):
        Parent().issue_credentials("Not A Valid Tenant!")


# --- P2 authentication -----------------------------------------------------------------------------------------------------------
def test_a_child_cannot_speak_as_another_child(net):
    parent, a, b = net
    forged = b.heartbeat()
    forged["child_id"] = a.child_id  # B's MAC, A's identity
    assert parent.receive(forged) == (False, "bad mac")
    tampered = a.heartbeat()
    tampered["payload"] = {**tampered["payload"], "ledger_length": 5}
    assert parent.receive(tampered) == (False, "bad mac")


# --- P3 replay -------------------------------------------------------------------------------------------------------------------
def test_replayed_and_out_of_order_messages_are_rejected(net):
    parent, a, _ = net
    first, second = a.heartbeat(), a.heartbeat()
    assert parent.receive(first)[0] and parent.receive(second)[0]
    assert parent.receive(second) == (False, "replayed or out-of-order sequence")
    assert parent.receive(first) == (False, "replayed or out-of-order sequence")


# --- P4 schema allowlist ---------------------------------------------------------------------------------------------------------
def hb(child, **override):
    payload = {"ledger_head": child.learner.ledger.head, "ledger_length": len(child.learner.ledger.entries), "params_sha256": "a" * 64}
    payload.update(override)
    return child.envelope("heartbeat", payload)


@pytest.mark.parametrize("override", [
    {"extra": "raw"}, {"params_sha256": "not-a-hash"}, {"params_sha256": "A" * 64}, {"ledger_length": True}, {"ledger_length": -1},
    {"ledger_length": 1.5}, {"ledger_head": ["a" * 64]}, {"ledger_head": {"x": 1}}, {"params_sha256": "a" * 65}])
def test_payloads_that_break_the_schema_are_rejected(net, override):
    parent, a, _ = net
    assert parent.receive(hb(a, **override)) == (False, "payload violates schema")


def test_missing_field_unknown_type_and_free_text_names_are_rejected(net):
    parent, a, _ = net
    assert parent.receive(a.envelope("heartbeat", {"ledger_head": "0" * 64}))[1] == "payload violates schema"
    assert parent.receive(a.envelope("telemetry", {"x": 1}))[1] == "unknown message type"
    leaky = a.envelope("checkpoint", {"name": "my private notes about a guest", "params_sha256": "a" * 64, "ledger_head": "0" * 64, "ledger_length": 0})
    assert parent.receive(leaky)[1] == "payload violates schema"


def test_nan_infinity_and_oversize_values_are_rejected(net):
    parent, a, _ = net
    assert parent.receive(a.evaluation("suite", "acc", float("nan"), 10))[1] == "payload violates schema"
    assert parent.receive(a.evaluation("suite", "acc", float("inf"), 10))[1] == "payload violates schema"
    big = a.envelope("heartbeat", {"ledger_head": "0" * 64, "ledger_length": 0, "params_sha256": "a" * 64, "pad": "x" * 5000})
    assert parent.receive(big)[1] == "payload too large"


@pytest.mark.parametrize("bad", [None, [], "text", 5, {}, {"child_id": "child-1"}, {"child_id": "child-1", "seq": 1, "type": "heartbeat", "payload": 3, "mac": "x"}])
def test_malformed_envelopes_never_crash_the_parent(net, bad):
    parent, a, _ = net
    assert parent.receive(bad)[0] is False
    assert parent.receive(a.heartbeat())[0]  # still alive and serving


def test_non_serialisable_payloads_are_rejected_not_crashing(net):
    parent, a, _ = net
    env = a.heartbeat()
    env["payload"] = {"ledger_head": {1, 2, 3}}
    assert parent.receive(env) == (False, "malformed envelope")


# --- P5 no raw leakage -----------------------------------------------------------------------------------------------------------
def test_a_canary_experience_never_appears_in_the_parents_state(net):
    parent, a, b = net
    canary = np.full(D, 0.123456789123)
    train(a, canary=canary)
    train(b, seed=5)
    for env in (a.heartbeat(), a.checkpoint("cp-1"), b.heartbeat(), a.evaluation("holdout", "accuracy", 0.8, 100)):
        assert parent.receive(env)[0]
    state = parent.export_state()
    secrets_to_find = ["0.123456789123", "0.12345678912", content_hash(0, canary, 0), content_hash(0, canary, 1), repr(float(a.learner.model.U[0, 0])),
                       repr(float(a.learner.model.V[0][0]))]
    assert not [s for s in secrets_to_find if s in state]


# --- P6 independence -------------------------------------------------------------------------------------------------------------
def test_training_one_child_does_not_touch_another_and_parent_holds_no_references(net):
    parent, a, b = net
    before = b.learner.model.params_hash()
    train(a)
    assert b.learner.model.params_hash() == before and a.learner.model.params_hash() != before
    assert a.learner.store is not b.learner.store and a.learner.ledger is not b.learner.ledger
    assert not any(isinstance(v, (Child, EventSourcedLearner)) for v in vars(parent).values())
    assert all(type(r).__name__ == "ChildRecord" for r in parent.registry.values())


# --- P7 anchored audit -----------------------------------------------------------------------------------------------------------
def test_honest_child_verifies_and_may_append_after_its_anchor(net):
    parent, a, _ = net
    train(a)
    assert parent.receive(a.heartbeat())[0] and parent.verify_child(a)
    train(a, n=3, seed=9)  # appends after the anchor
    assert parent.verify_child(a)


def test_rewritten_or_truncated_history_fails_the_anchor_even_with_valid_links(net):
    parent, a, _ = net
    train(a)
    assert parent.receive(a.heartbeat())[0]
    forged = Ledger()  # same entries but one changed, hashes recomputed: links alone verify
    for e in a.learner.ledger.entries:
        forged.add(e.task_id, e.kind, e.text if e.version != 2 else "{}", e.run_id, e.seed)
    assert forged.verify()
    original = a.learner.ledger
    a.learner.ledger = forged
    assert not parent.verify_child(a)
    truncated = Ledger()
    for e in original.entries[:3]:
        truncated.add(e.task_id, e.kind, e.text, e.run_id, e.seed)
    a.learner.ledger = truncated
    assert not parent.verify_child(a)


def test_anchor_regression_and_fork_are_rejected(net):
    parent, a, _ = net
    train(a)
    assert parent.receive(a.heartbeat())[0]
    assert parent.receive(hb(a, ledger_length=1, ledger_head=a.learner.ledger.entries[0].hash))[1] == "anchor regression"
    n = len(a.learner.ledger.entries)
    assert parent.receive(hb(a, ledger_length=n, ledger_head="b" * 64))[1] == "anchor fork"


# --- P8 checkpoint integrity -----------------------------------------------------------------------------------------------------
def test_restore_checks_the_parents_recorded_hash(net):
    parent, a, _ = net
    train(a)
    assert parent.receive(a.checkpoint("cp-1"))[0]
    recorded = parent.registry[a.child_id].checkpoints["cp-1"]
    train(a, n=4, seed=3)
    assert a.restore("cp-1", recorded) and a.learner.model.params_hash() == recorded
    a.learner.checkpoints["cp-1"].U = a.learner.checkpoints["cp-1"].U + 1.0  # tamper with the local copy
    assert not a.restore("cp-1", recorded)
    assert not a.restore("missing", recorded)


# --- P9 audit trail --------------------------------------------------------------------------------------------------------------
def test_parent_audit_chain_records_every_event_kind_and_verifies(net):
    parent, a, b = net
    train(a)
    parent.receive(a.heartbeat())
    parent.receive(a.checkpoint("cp-1"))
    parent.receive(a.evaluation("holdout", "accuracy", 0.7, 50))
    parent.receive({"child_id": "nobody", "seq": 1, "type": "heartbeat", "payload": {}, "mac": "x"})
    parent.revoke(b.child_id)
    kinds = [e.kind for e in parent.ledger.entries]
    assert kinds.count("registration") == 2 and kinds.count("rejection") == 1 and kinds.count("revocation") == 1
    assert {"heartbeat", "checkpoint", "evaluation"} <= set(kinds)
    assert parent.ledger.verify()
    parent.ledger.entries[1] = dataclasses.replace(parent.ledger.entries[1], text="{}")
    assert not parent.ledger.verify()


def test_exported_state_is_valid_json_without_secrets(net):
    parent, a, _ = net
    state = json.loads(parent.export_state())
    assert set(state) == {"registry", "ledger"}
    assert a._key.hex() not in parent.export_state()
