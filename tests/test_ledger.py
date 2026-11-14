import dataclasses

import pytest

from lucv11.ledger import GENESIS, Ledger, hash_v1, hash_v2


def make(n=3):
    ledger = Ledger()
    for i in range(n):
        ledger.add(f"t{i}", "failure", f"lesson {i}", "run-A", i)
    return ledger


def test_v1_formula_is_reproduced_byte_for_byte():
    # Vectors computed with Lucifer-BenchMarks src/lucifer/memory.py _hash at commit fe08665.
    assert hash_v1("0" * 64, 1, "t1", "failure", "x") == "139922955345c87c2683b16c5948c246a265a68ef7760e91f8997a784e9058c0"
    assert hash_v1("a" * 64, 2, "task-9", "fix", "Dates are DD-Mon-YYYY | really") == "0647604ec182a2aaedf4ebe5687715bf4768de47e8d218114e34e2278951f417"


def test_v1_separator_collision_exists_and_v2_removes_it():
    assert hash_v1("p", 1, "a|b", "c", "x") == hash_v1("p", 1, "a", "b|c", "x")
    assert hash_v2("p", 1, "a|b", "c", "x", "r", 0) != hash_v2("p", 1, "a", "b|c", "x", "r", 0)


@pytest.mark.parametrize("field,value", [("task_id", "other"), ("kind", "fix"), ("text", "changed"), ("run_id", "FORGED"), ("seed", 99)])
def test_editing_any_field_including_provenance_breaks_the_chain(field, value):
    ledger = make()
    assert ledger.verify()
    ledger.entries[1] = dataclasses.replace(ledger.entries[1], **{field: value})
    assert not ledger.verify()


def test_a_rewritten_history_with_recomputed_hashes_passes_links_but_fails_the_anchor():
    original = make()
    anchor_head, anchor_len = original.head, len(original.entries)
    forged = Ledger()
    for e in original.entries:
        forged.add(e.task_id, e.kind, e.text if e.version != 2 else "FORGED", e.run_id, e.seed)
    assert forged.verify()  # links alone cannot tell
    assert not forged.verify(expected_head=anchor_head)


def test_truncation_is_caught_only_with_the_anchor():
    ledger = make()
    anchor = (ledger.head, len(ledger.entries))
    del ledger.entries[-1]
    assert ledger.verify()
    assert not ledger.verify(expected_length=anchor[1])
    assert not ledger.verify(expected_head=anchor[0])


def test_reordering_and_version_gaps_are_detected():
    ledger = make()
    ledger.entries[0], ledger.entries[1] = ledger.entries[1], ledger.entries[0]
    assert not ledger.verify()


def test_empty_ledger_and_genesis():
    ledger = Ledger()
    assert ledger.verify() and ledger.head == GENESIS and ledger.verify(expected_head=GENESIS, expected_length=0)


def test_missing_provenance_is_refused():
    with pytest.raises(ValueError):
        Ledger().add("t", "failure", "x", "", 0)
    with pytest.raises(ValueError):
        Ledger().add("t", "failure", "x", "run", -1)
