import numpy as np

from lucv11.ledger import GENESIS, Ledger
from lucv11.m5 import _examples, accuracy, make_world, run_world, train_model


def test_prefix_check_accepts_appends_and_rejects_rewrites():
    ledger = Ledger()
    for i in range(4):
        ledger.add(f"t{i}", "failure", f"lesson {i}", "run", i)
    head2, head4 = ledger.entries[1].hash, ledger.head
    assert ledger.verify_prefix(head2, 2) and ledger.verify_prefix(head4, 4) and ledger.verify_prefix(GENESIS, 0)
    ledger.add("t4", "fix", "later", "run", 4)
    assert ledger.verify_prefix(head2, 2)
    assert not ledger.verify_prefix(head2, 3) and not ledger.verify_prefix(head4, 9)


def test_world_is_deterministic_and_rules_agree_or_conflict_as_named():
    a, b = make_world(2, True), make_world(2, True)
    assert all(np.array_equal(x[1], y[1]) for x, y in zip(a["tenants"][0]["train"], b["tenants"][0]["train"]))
    for same, lo, hi in ((True, 0.70, 1.0), (False, 0.0, 0.60)):  # a model trained on tenant A, scored on tenant B
        w = make_world(0, same)
        model = train_model(0, _examples(w["tenants"][0]["train"]), 0)
        assert lo <= accuracy(model, w["tenants"][1]["test"]) <= hi


def test_run_world_is_deterministic_and_returns_both_arms():
    assert run_world(1, False) == run_world(1, False)
    assert set(run_world(1, True)) == {"personal", "pooled"}
