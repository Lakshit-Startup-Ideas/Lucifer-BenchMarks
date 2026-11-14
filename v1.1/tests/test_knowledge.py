import dataclasses
import json

import numpy as np
import pytest

from lucv11.distributed import Child, Parent
from lucv11.knowledge import CONFLICT_MARGIN, PEER_MARGIN, KnowledgeBase, Reviewer, cosine
from lucv11.learner import D
from lucv11.ledger import Ledger
from lucv11.m6 import Peer, make_world, poison_rule, run_seed


@pytest.fixture
def lab():
    parent = Parent()
    ids = {t: parent.issue_credentials(f"tenant-{t}") for t in ("a", "m")}
    kids = {t: Child(cid, f"tenant-{t}", key, i) for i, (t, (cid, key)) in enumerate(ids.items())}
    rng = np.random.default_rng(0)
    for i in range(12):
        kids["a"].observe_and_learn(i % 2, rng.normal(size=D), int(rng.integers(0, 2)))
    for kid in kids.values():
        assert parent.receive(kid.checkpoint("cp-1"))[0]
    kb = KnowledgeBase()
    reviewer = Reviewer(parent, kb)
    pkg = {**kids["a"].export_package(0, "cp-1"), "pkg_id": reviewer.new_id()}
    return parent, kids, kb, reviewer, pkg


def test_an_honest_package_passes_the_metadata_checks(lab):
    parent, kids, kb, reviewer, pkg = lab
    assert reviewer.deterministic(pkg, kids["a"]) == []
    assert abs(np.linalg.norm(pkg["rule"]) - 1.0) < 1e-9


def test_a_poisoned_package_with_valid_metadata_also_passes_them(lab):
    parent, kids, kb, reviewer, pkg = lab
    bad = kids["m"].export_package(0, "cp-1", rule=poison_rule("flip", np.array(pkg["rule"]), np.random.default_rng(1)))
    assert reviewer.deterministic({**bad, "pkg_id": "pkg-9"}, kids["m"]) == []  # why a deterministic reviewer alone is not enough


@pytest.mark.parametrize("change,reason", [
    ({"consent": False}, "no consent"), ({"consent": None}, "no consent"), ({"checkpoint": "nope"}, "checkpoint not recorded"),
    ({"params_sha256": "0" * 64}, "checkpoint hash mismatch"), ({"ledger_length": 1}, "anchor mismatch"), ({"ledger_head": "f" * 64}, "anchor mismatch"),
    ({"rule": [0.5] * (D - 1)}, "rule invalid length"), ({"rule": "text"}, "rule invalid length"),
    ({"rule": [float("nan")] + [0.0] * (D - 1)}, "rule not finite"), ({"rule": [float("inf")] + [0.0] * (D - 1)}, "rule not finite"),
    ({"rule": [1] * D}, "rule not finite"), ({"rule": [0.5] * D}, "rule norm")])
def test_each_deterministic_rejection_reason_fires(lab, change, reason):
    parent, kids, kb, reviewer, pkg = lab
    assert reason in reviewer.deterministic({**pkg, **change}, kids["a"])


def test_revoked_or_unknown_origin_and_rewritten_history_are_rejected(lab):
    parent, kids, kb, reviewer, pkg = lab
    assert reviewer.deterministic({**pkg, "origin": "child-404"}, kids["a"]) == ["origin unknown or revoked"]
    forged = Ledger()
    for e in kids["a"].learner.ledger.entries:
        forged.add(e.task_id, e.kind, e.text if e.version != 3 else "{}", e.run_id, e.seed)
    kids["a"].learner.ledger = forged
    assert "origin history not verified" in reviewer.deterministic(pkg, kids["a"])
    parent.revoke(kids["a"].child_id)
    assert reviewer.deterministic(pkg, kids["a"]) == ["origin unknown or revoked"]


def test_promotion_is_a_versioned_chain_entry_with_provenance_and_evidence(lab):
    parent, kids, kb, reviewer, pkg = lab
    v = kb.promote(pkg, {"peers": {"child-9": {"pkg_acc": 0.8, "local_acc": 0.6}}})
    entry = json.loads(kb.ledger.entries[-1].text)
    assert v == 1 and entry["package"]["checkpoint"] == "cp-1" and entry["evidence"]["peers"] and kb.verify()
    assert kb.current()[0]["pkg_id"] == pkg["pkg_id"]


def test_rollback_restores_the_exact_earlier_state_and_keeps_the_archive(lab):
    parent, kids, kb, reviewer, pkg = lab
    kb.promote({**pkg, "pkg_id": "pkg-1"}, {})
    hash_v1 = kb.state_hash()
    kb.promote({**pkg, "pkg_id": "pkg-2", "ctx": 1}, {})
    kb.promote({**pkg, "pkg_id": "pkg-3"}, {})
    assert kb.state_hash() != hash_v1 and kb.current()[0]["pkg_id"] == "pkg-3"
    kb.rollback(1, "found harmful")
    assert kb.state_hash() == hash_v1 and set(kb.current()) == {0}
    assert {p["pkg_id"] for p in kb.archived()} == {"pkg-2", "pkg-3"}
    v = kb.promote({**pkg, "pkg_id": "pkg-4"}, {})
    assert v == 4 and kb.current()[0]["pkg_id"] == "pkg-4"  # version ids are never reused
    assert kb.verify() and len(kb.ledger.entries) == 5


def test_rollback_to_an_unknown_version_is_refused(lab):
    parent, kids, kb, reviewer, pkg = lab
    with pytest.raises(ValueError):
        kb.rollback(5, "x")


def test_editing_or_deleting_a_log_entry_is_detected(lab):
    parent, kids, kb, reviewer, pkg = lab
    for i in range(3):
        kb.promote({**pkg, "pkg_id": f"pkg-{i}", "ctx": i}, {})
    kb.ledger.entries[1] = dataclasses.replace(kb.ledger.entries[1], text=kb.ledger.entries[1].text.replace("pkg-1", "pkg-X"))
    assert not kb.verify()
    kb2 = KnowledgeBase()
    for i in range(3):
        kb2.promote({**pkg, "pkg_id": f"pkg-{i}", "ctx": i}, {})
    del kb2.ledger.entries[1]
    assert not kb2.verify()


def test_conflicting_packages_need_a_larger_peer_gain(lab):
    parent, kids, kb, reviewer, pkg = lab
    kb.promote(pkg, {})
    agree = np.array(pkg["rule"])
    opposite = {**pkg, "rule": [float(v) for v in -agree], "pkg_id": "pkg-7"}
    similar = {**pkg, "pkg_id": "pkg-8"}
    gain = lambda g: {"p1": {"pkg_acc": 0.6 + g, "local_acc": 0.6}, "p2": {"pkg_acc": 0.6 + g, "local_acc": 0.6}}
    assert cosine(agree, opposite["rule"]) < 0 and reviewer.required_margin(opposite) == CONFLICT_MARGIN
    assert reviewer.required_margin(similar) == PEER_MARGIN
    assert not reviewer.peers_agree(opposite, gain(0.07)) and reviewer.peers_agree(opposite, gain(0.12))
    assert reviewer.peers_agree(similar, gain(0.07)) and not reviewer.peers_agree(similar, gain(0.03))


def test_one_unconvinced_peer_blocks_and_no_evidence_blocks(lab):
    parent, kids, kb, reviewer, pkg = lab
    mixed = {"p1": {"pkg_acc": 0.9, "local_acc": 0.6}, "p2": {"pkg_acc": 0.55, "local_acc": 0.6}}
    assert not reviewer.peers_agree(pkg, mixed) and not reviewer.peers_agree(pkg, {})


def test_peer_review_uses_the_protocol_and_leaks_no_validation_data(lab):
    parent, kids, kb, reviewer, pkg = lab
    world = make_world(0)
    canary_val = world["data"]["B"]["val"]
    peer_id, peer_key = parent.issue_credentials("tenant-b")
    peer = Peer(Child(peer_id, "tenant-b", peer_key, 9), canary_val)
    evidence = reviewer.peer_evidence(pkg, [peer])
    assert set(evidence[peer_id]) == {"pkg_acc", "local_acc"}
    state = parent.export_state()
    assert repr(float(canary_val[0][0][0, 0])) not in state and str(canary_val[0][0][0, 0])[:10] not in state
    assert [r["suite"] for r in parent.registry[peer_id].evaluations] == [pkg["pkg_id"]] * 2


def test_the_experiment_is_deterministic_per_seed():
    assert run_seed(1) == run_seed(1)
