import pytest

from lucifer.sandbox import SandboxExecutor, extract_code
from lucifer.tasks import FAMILIES, TASKS, by_split, task_set

executor = SandboxExecutor()


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_reference_passes_and_naive_fails(task):
    assert executor.run(task, task.reference).passed, "the reference solution must pass its own tests"
    naive = executor.run(task, task.naive)
    assert not naive.passed, "the naive solution must be caught by the tests"
    assert naive.feedback  # a failure always says what failed


def test_task_set_shape():
    assert len({t.id for t in TASKS}) == len(TASKS) == 80
    for name, size in (("pitfall", 50), ("convention", 30), ("all", 80)):
        assert len(task_set(name)) == size
    for family in FAMILIES:
        for split, expected in (("exp", 3), ("sim", 2 if family in ("empty", "range", "order", "text", "interval", "money", "parse", "boundary") else 3)):
            assert sum(1 for t in TASKS if t.family == family and t.split == split) == expected, (family, split)
    assert len(by_split("xfer")) == 16 and all(t.family == "mixed" for t in by_split("xfer"))
    assert all(len(t.tests) >= 3 for t in TASKS)
    assert len(by_split("sim", task_set("pitfall"))) + len(by_split("xfer", task_set("pitfall"))) == 26
    assert len(by_split("sim", task_set("convention"))) + len(by_split("xfer", task_set("convention"))) == 12 + 6
    with pytest.raises(ValueError):
        task_set("nope")


def test_convention_tasks_hide_their_convention_from_the_spec():
    """The point of the convention set: nothing in the task text says how identifiers, prices, dates or error messages must look."""
    for t in task_set("convention"):
        words = t.spec.replace(f"`{t.entry}", "").lower()  # the function name itself may say format_*
        if t.family == "ident":
            assert "00" not in words and "pad" not in words and "prefix" not in words
        if t.family == "price":
            assert "₹" not in words and "comma" not in words and "decimal" not in words and "separator" not in words
        if t.family == "date":
            assert "mar" not in words.split() and "dd" not in words and "month name" not in words
        if t.family == "errors":
            assert "invalid" not in words and "message" not in words


def test_sandbox_reports_errors_timeouts_and_missing_function():
    task = TASKS[0]
    assert "NameError" in executor.run(task, "def other():\n    pass").feedback or "check failed" in executor.run(task, "def other():\n    pass").feedback
    assert "SyntaxError" in executor.run(task, "def mean(:").feedback
    slow = SandboxExecutor(timeout_s=1.5).run(task, "def mean(nums):\n    while True:\n        pass")
    assert not slow.passed and "did not finish" in slow.feedback


def test_extract_code():
    assert extract_code("Sure!\n```python\ndef f():\n    return 1\n```\nDone.") == "def f():\n    return 1"
    assert extract_code("def g():\n    pass") == "def g():\n    pass"
