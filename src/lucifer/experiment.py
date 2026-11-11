"""Runs the experiment described in docs/EXPERIMENT-PLAN.md: conditions x seeds x (experience phase, frozen evaluation phase)."""
from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from .agent import build_prompt, failure_lesson, fix_lesson, retry_prompt
from .backends.base import Backend
from .memory import Memory
from .retrieval import least_relevant, relevant
from .sandbox import Executor, extract_code
from .tasks import Task, by_split

CONDITIONS = ("baseline", "lucifer", "irrelevant")
PHASES = ("experience", "similar", "transfer", "replay")


@dataclass
class Config:
    backend: Backend
    executor: Executor
    seeds: tuple[int, ...] = (0, 1, 2, 3, 4)
    conditions: tuple[str, ...] = CONDITIONS
    k: int = 3  # lessons shown per task
    retries: int = 1
    run_id: str = "run"
    out_dir: Path | None = None


@dataclass
class Result:
    rows: list[dict] = field(default_factory=list)  # one per task attempt-sequence
    attempts: list[dict] = field(default_factory=list)  # one per model call
    audits: list[dict] = field(default_factory=list)  # one per memory-using run


def _solve(cfg: Config, task: Task, phase: str, seed: int, condition: str, memory: Memory | None, out: Result) -> tuple[bool, list[str]]:
    """Returns (passed on the first attempt, ids of lessons shown). One retry with the test output, the same for every condition."""
    shown = []
    if condition == "lucifer" and memory is not None:
        shown = relevant(task.spec + " " + task.entry, memory.lessons(), cfg.k)
    elif condition == "irrelevant" and memory is not None:
        shown = least_relevant(task.spec + " " + task.entry, memory.lessons(), cfg.k)
    base_prompt = build_prompt(task, [l.text for l in shown])
    prompt, code, feedback, passed_first, passed_any = base_prompt, "", "", False, False
    t0 = time.perf_counter()
    prompt_tokens = completion_tokens = 0
    attempts_used = 0
    for attempt in range(1, cfg.retries + 2):
        gen = cfg.backend.generate(prompt, seed=seed * 1000 + attempt, task=task)
        code = extract_code(gen.text)
        result = cfg.executor.run(task, code)
        attempts_used = attempt
        prompt_tokens += gen.prompt_tokens
        completion_tokens += gen.completion_tokens
        out.attempts.append({"run_id": cfg.run_id, "seed": seed, "condition": condition, "phase": phase, "task_id": task.id, "attempt": attempt,
                             "passed": result.passed, "model_ms": gen.ms, "exec_ms": result.ms, "feedback": result.feedback, "code": code})
        if result.passed:
            passed_any = True
            passed_first = attempt == 1
            break
        feedback = result.feedback
        prompt = retry_prompt(base_prompt, code, feedback)
        if attempt == 1:
            first_failure = feedback
    if phase == "experience" and memory is not None:  # learning happens only here; evaluation is frozen
        if not passed_first:
            memory.add(task.id, "failure", failure_lesson(task, first_failure), cfg.run_id, seed)
        if passed_any and not passed_first:
            memory.add(task.id, "fix", fix_lesson(task, code), cfg.run_id, seed)
    out.rows.append({"run_id": cfg.run_id, "seed": seed, "condition": condition, "phase": phase, "task_id": task.id, "family": task.family,
                     "pass_at_1": passed_first, "pass_at_2": passed_any, "attempts": attempts_used, "lessons_shown": [l.id for l in shown],
                     "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "wall_ms": (time.perf_counter() - t0) * 1000,
                     "memory_version": memory.version if memory is not None else 0})
    return passed_first, [str(l.id) for l in shown]


def run_experiment(cfg: Config, progress=None) -> Result:
    out = Result()
    experience, similar, transfer = by_split("exp"), by_split("sim"), by_split("xfer")
    for seed in cfg.seeds:
        order_rng = random.Random(f"order-{seed}")
        exp_order = experience[:]
        order_rng.shuffle(exp_order)
        eval_items = [(t, "similar") for t in similar] + [(t, "transfer") for t in transfer] + [(t, "replay") for t in experience]
        order_rng.shuffle(eval_items)  # the same order for every condition within a seed
        for condition in cfg.conditions:
            memory = Memory() if condition != "baseline" else None
            for task in exp_order:
                _solve(cfg, task, "experience", seed, condition, memory, out)
            if memory is not None:
                out.audits.append({"seed": seed, "condition": condition, **memory.audit()})
            for task, phase in eval_items:
                _solve(cfg, task, phase, seed, condition, memory, out)
            if progress:
                progress(seed, condition)
    if cfg.out_dir:
        cfg.out_dir.mkdir(parents=True, exist_ok=True)
        (cfg.out_dir / "rows.json").write_text(json.dumps(out.rows))
        (cfg.out_dir / "audits.json").write_text(json.dumps(out.audits))
        (cfg.out_dir / "attempts.jsonl").write_text("\n".join(json.dumps(a) for a in out.attempts) + "\n")
        (cfg.out_dir / "meta.json").write_text(json.dumps({"backend": cfg.backend.name, "seeds": list(cfg.seeds), "k": cfg.k, "retries": cfg.retries, "run_id": cfg.run_id}))
    return out
