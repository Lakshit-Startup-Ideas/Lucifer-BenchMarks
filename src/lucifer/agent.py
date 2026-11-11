"""Prompts and the two kinds of lesson. Kept in one small place so the experiment is easy to read and to pin."""
from __future__ import annotations

from .tasks import Task

NOTES_HEADER = "Notes from earlier tasks (they may or may not apply to this one):"
RETRY_MARKER = "Your previous attempt failed."


def build_prompt(task: Task, notes: list[str]) -> str:
    if not notes:
        return task.prompt
    return NOTES_HEADER + "\n" + "\n".join(f"- {n}" for n in notes) + "\n\n" + task.prompt


def retry_prompt(base_prompt: str, previous_code: str, feedback: str) -> str:
    return f"{base_prompt}\n\n{RETRY_MARKER}\n```python\n{previous_code}\n```\n{feedback}\nReply with the corrected function in one ```python code block."


def failure_lesson(task: Task, feedback: str) -> str:
    return f"A first attempt at '{task.entry}' failed. The spec said: {task.spec} {feedback}"


def fix_lesson(task: Task, fixed_code: str) -> str:
    return f"For '{task.entry}' ({task.spec}) this version passed after a failed first attempt:\n{fixed_code[:500]}"
