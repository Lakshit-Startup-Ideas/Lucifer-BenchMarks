import pytest

from lucifer.memory import GENESIS, Memory
from lucifer.retrieval import least_relevant, relevant
from lucifer.tasks import BY_ID


def filled(n=5) -> Memory:
    m = Memory()
    for i in range(n):
        m.add(f"t{i}", "failure", f"lesson number {i} about empty lists", "run-1", i)
    return m


def test_chain_verifies_and_versions_count_up():
    m = filled()
    assert m.version == 5 and len(m) == 5 and m.verify_chain()
    assert [l.version for l in m.lessons()] == [1, 2, 3, 4, 5]
    assert Memory().head_hash == GENESIS


def test_changing_an_old_lesson_is_detected():
    m = filled()
    m.db.execute("UPDATE lessons SET text = 'rewritten' WHERE version = 2")
    m.db.commit()
    assert not m.verify_chain()
    assert not m.audit()["ok"]


def test_deleting_a_lesson_is_detected():
    m = filled()
    m.db.execute("DELETE FROM lessons WHERE version = 3")
    m.db.commit()
    assert not m.verify_chain()


def test_rollback_restores_the_exact_earlier_state_and_archives_the_rest():
    m = filled(6)
    at3 = [(l.version, l.hash) for l in m.lessons() if l.version <= 3]
    head3 = m.lessons()[2].hash
    m.rollback(3)
    assert m.version == 3 and m.head_hash == head3 and [(l.version, l.hash) for l in m.lessons()] == at3
    assert m.verify_chain()
    assert m.db.execute("SELECT COUNT(*) FROM archived").fetchone()[0] == 3  # undone, but kept for audit
    m.add("t9", "fix", "new branch", "run-2", 1)  # the history can continue after a rollback
    assert m.verify_chain() and m.version == 4
    with pytest.raises(ValueError):
        m.rollback(99)


def test_audit_works_on_a_copy_and_leaves_the_original_alone():
    m = filled(6)
    before = [(l.version, l.hash) for l in m.lessons()]
    report = m.audit()
    assert report["ok"] and report["lessons"] == 6
    assert [(l.version, l.hash) for l in m.lessons()] == before


def test_every_lesson_records_where_it_came_from():
    m = filled(3)
    assert all(l.task_id and l.run_id == "run-1" and l.seed >= 0 for l in m.lessons())


def test_retrieval_prefers_the_matching_lesson_and_the_control_picks_the_opposite():
    m = Memory()
    m.add("a", "failure", "The spec said: returns the mean of a list and 0.0 for an empty list.", "r", 0)
    m.add("b", "failure", "The spec said: sorts words by length and alphabetically among equal lengths.", "r", 0)
    m.add("c", "failure", "The spec said: counts the integers from a to b including both ends.", "r", 0)
    task = BY_ID["empty-4"]
    top = relevant(task.spec + " " + task.entry, m.lessons(), k=1)
    assert top and top[0].task_id == "a"
    worst = least_relevant(task.spec + " " + task.entry, m.lessons(), k=1)
    assert worst and worst[0].task_id != "a"
    assert relevant("anything", [], k=3) == [] and least_relevant("anything", [], k=3) == []
