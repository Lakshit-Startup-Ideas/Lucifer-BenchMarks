"""Runs the experiment described in docs/EXPERIMENT-PLAN.md: conditions x seeds x (experience phase, frozen evaluation phase)."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from .agent import build_prompt, failure_lesson, fix_lesson, retry_prompt
from .backends.base import Backend
from .memory import Memory
from .retrieval import least_relevant, relevant
from .sandbox import Executor, extract_code
from .tasks import TASKS, Task, by_split
from .tracing import Tracer

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
    tasks: tuple[Task, ...] | None = None  # the task set to run; default is every task


@dataclass
class Result:
    rows: list[dict] = field(default_factory=list)  # one per task attempt-sequence
    attempts: list[dict] = field(default_factory=list)  # one per model call
    audits: list[dict] = field(default_factory=list)  # one per memory-using run
    spans: list[dict] = field(default_factory=list)  # every step of every solve (see tracing.py)
    memories: list[dict] = field(default_factory=list)  # the lessons each memory store held after the experience phase


def _solve(cfg: Config, task: Task, phase: str, seed: int, condition: str, memory: Memory | None, out: Result) -> tuple[bool, list[str]]:
    """Returns (passed on the first attempt, ids of lessons shown). One retry with the test output, the same for every condition."""
    trace_id = f"{cfg.run_id}/s{seed}/{condition}/{phase}/{task.id}"
    tr = Tracer(trace_id, f"solve {task.id}", task_id=task.id, family=task.family, phase=phase, seed=seed, condition=condition, backend=cfg.backend.name)
    simulated = cfg.backend.name.startswith("sim-")

    shown = []
    with tr.span("retrieve_memory", "retrieval", mode=condition, k=cfg.k, memory_lessons=len(memory) if memory is not None else 0) as sp:
        if condition == "lucifer" and memory is not None:
            shown = relevant(task.spec + " " + task.entry, memory.lessons(), cfg.k)
        elif condition == "irrelevant" and memory is not None:
            shown = least_relevant(task.spec + " " + task.entry, memory.lessons(), cfg.k)
        sp.set(lessons_shown=[{"id": l.id, "version": l.version, "task_id": l.task_id, "kind": l.kind, "text": l.text[:300]} for l in shown])
    base_prompt = build_prompt(task, [l.text for l in shown])
    with tr.span("build_prompt", "prompt", prompt_chars=len(base_prompt), notes=len(shown)):
        pass

    prompt, code, feedback, first_failure = base_prompt, "", "", ""
    passed_first = passed_any = False
    prompt_tokens = completion_tokens = attempts_used = 0
    for attempt in range(1, cfg.retries + 2):
        with tr.span(f"attempt {attempt}", "attempt", attempt=attempt, retry=attempt > 1) as at:
            with tr.span("llm.generate", "llm", model=cfg.backend.name, seed=seed * 1000 + attempt, simulated=simulated, prompt=prompt[:6000]) as g:
                gen = cfg.backend.generate(prompt, seed=seed * 1000 + attempt, task=task)
                g.duration_ms = gen.ms
                g.set(prompt_tokens=gen.prompt_tokens, completion_tokens=gen.completion_tokens, reply=gen.text[:4000])
            code = extract_code(gen.text)
            with tr.span("sandbox.run_tests", "execution", tests=len(task.tests), code=code[:3000]) as ex:
                result = cfg.executor.run(task, code)
                ex.duration_ms = result.ms
                ex.status = "ok" if result.passed else "error"
                ex.set(passed=result.passed, feedback=result.feedback)
            at.status = "ok" if result.passed else "error"
            at.set(passed=result.passed)
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
        with tr.span("memory.write", "memory", store_version_before=memory.version) as mw:
            written = []
            if not passed_first:
                written.append(memory.add(task.id, "failure", failure_lesson(task, first_failure), cfg.run_id, seed))
            if passed_any and not passed_first:
                written.append(memory.add(task.id, "fix", fix_lesson(task, code), cfg.run_id, seed))
            mw.set(lessons_written=[{"id": l.id, "version": l.version, "kind": l.kind, "hash": l.hash[:12], "text": l.text[:300]} for l in written], store_version_after=memory.version)
    spans = tr.finish("ok" if passed_any else "error", pass_at_1=passed_first, pass_at_2=passed_any, attempts=attempts_used)
    out.spans.extend(spans)
    out.rows.append({"run_id": cfg.run_id, "trace_id": trace_id, "seed": seed, "condition": condition, "phase": phase, "task_id": task.id, "family": task.family,
                     "pass_at_1": passed_first, "pass_at_2": passed_any, "attempts": attempts_used, "lessons_shown": [l.id for l in shown],
                     "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "wall_ms": round(tr.root.duration_ms, 3),
                     "memory_version": memory.version if memory is not None else 0})
    return passed_first, [str(l.id) for l in shown]


def run_experiment(cfg: Config, progress=None) -> Result:
    out = Result()
    pool = cfg.tasks if cfg.tasks is not None else TASKS
    experience, similar, transfer = by_split("exp", pool), by_split("sim", pool), by_split("xfer", pool)
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
                out.memories.append({"seed": seed, "condition": condition, "lessons": [{"id": l.id, "version": l.version, "task_id": l.task_id, "kind": l.kind, "text": l.text, "run_id": l.run_id, "seed": l.seed, "hash": l.hash} for l in memory.lessons()]})
            for task, phase in eval_items:
                _solve(cfg, task, phase, seed, condition, memory, out)
            if progress:
                progress(seed, condition)
    if cfg.out_dir:
        cfg.out_dir.mkdir(parents=True, exist_ok=True)
        (cfg.out_dir / "rows.json").write_text(json.dumps(out.rows))
        (cfg.out_dir / "audits.json").write_text(json.dumps(out.audits))
        (cfg.out_dir / "attempts.jsonl").write_text("\n".join(json.dumps(a) for a in out.attempts) + "\n")
        (cfg.out_dir / "spans.jsonl").write_text("\n".join(json.dumps(sp) for sp in out.spans) + "\n")
        (cfg.out_dir / "memories.json").write_text(json.dumps(out.memories))
        (cfg.out_dir / "meta.json").write_text(json.dumps({"backend": cfg.backend.name, "seeds": list(cfg.seeds), "k": cfg.k, "tasks": len(pool), "retries": cfg.retries, "run_id": cfg.run_id}))
    return out
