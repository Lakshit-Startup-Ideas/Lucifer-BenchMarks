import pytest

from lucifer.sandbox import SandboxExecutor, extract_code
from lucifer.tasks import FAMILIES, TASKS, by_split

executor = SandboxExecutor()


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_reference_passes_and_naive_fails(task):
    assert executor.run(task, task.reference).passed, "the reference solution must pass its own tests"
    naive = executor.run(task, task.naive)
    assert not naive.passed, "the naive solution must be caught by the tests"
    assert naive.feedback  # a failure always says what failed


def test_task_set_shape():
    assert len({t.id for t in TASKS}) == len(TASKS)
    for family in FAMILIES:
        assert sum(1 for t in TASKS if t.family == family and t.split == "exp") == 3
        assert sum(1 for t in TASKS if t.family == family and t.split == "sim") == 2
    assert len(by_split("xfer")) == 10 and all(t.family == "mixed" for t in by_split("xfer"))
    assert all(len(t.tests) >= 3 for t in TASKS)
    assert len(TASKS) == 50 and len(by_split("sim")) + len(by_split("xfer")) == 26


def test_sandbox_reports_errors_timeouts_and_missing_function():
    task = TASKS[0]
    assert "NameError" in executor.run(task, "def other():\n    pass").feedback or "check failed" in executor.run(task, "def other():\n    pass").feedback
    assert "SyntaxError" in executor.run(task, "def mean(:").feedback
    slow = SandboxExecutor(timeout_s=1.5).run(task, "def mean(nums):\n    while True:\n        pass")
    assert not slow.passed and "did not finish" in slow.feedback


def test_extract_code():
    assert extract_code("Sure!\n```python\ndef f():\n    return 1\n```\nDone.") == "def f():\n    return 1"
    assert extract_code("def g():\n    pass") == "def g():\n    pass"
