"""The controls: before trusting any result on a real model, the measuring machinery must say the right thing about agents whose
behaviour we know. A fast stand-in executor is used here so hundreds of simulated experiments take seconds; tests/test_pipeline.py
runs the real sandbox."""
from lucifer.backends.sim import SimBackend
from lucifer.experiment import Config, run_experiment
from lucifer.gates import evaluate
from lucifer.sandbox import FastExecutor


def experiment(kind, index, base=0.4, effect=0.4, seeds=5):
    cfg = Config(SimBackend(kind, base=base, effect=effect), FastExecutor(), seeds=tuple(range(index * seeds, index * seeds + seeds)))
    result = run_experiment(cfg)
    return evaluate(result.rows, result.audits, resamples=1500)


def test_an_agent_that_cannot_learn_is_almost_never_reported_as_improving():
    runs = 40
    false_positives = sum(experiment("null", i)["gate1_improvement"]["passed"] for i in range(runs))
    assert false_positives / runs <= 0.10, f"{false_positives}/{runs} false positives"


def with_more_tasks(monkeypatch, copies):
    """Stands in for a bigger task set: the same tasks repeated under new ids (each gets its own random draws)."""
    import dataclasses

    import lucifer.backends.sim as sim
    import lucifer.tasks as tasks

    many = tuple(dataclasses.replace(t, id=f"{t.id}#{k}") for k in range(copies) for t in tasks.TASKS)
    monkeypatch.setattr(tasks, "TASKS", many)
    monkeypatch.setattr(sim, "TASKS", many)


def only_original_families(monkeypatch):
    """The first version of the task set (four families, 12 similar+transfer tasks), to document how little power that had."""
    import lucifer.backends.sim as sim
    import lucifer.tasks as tasks

    keep = tuple(t for t in tasks.TASKS if t.family in ("empty", "range", "order", "text", "mixed") and int(t.id.split("-")[1]) <= (4 if t.family == "mixed" else 5))
    monkeypatch.setattr(tasks, "TASKS", keep)
    monkeypatch.setattr(sim, "TASKS", keep)
    return keep


def test_a_set_with_only_12_primary_tasks_misses_a_real_effect_so_it_must_not_be_trusted(monkeypatch):
    """With only 12 similar+transfer tasks a genuine +20 point effect passes both comparisons well under half the time (about 1 in 3 in the
    60-run power study in docs/EXPERIMENT-PLAN.md). This is why the task set was enlarged."""
    keep = only_original_families(monkeypatch)
    assert sum(t.split in ("sim", "xfer") for t in keep) == 12
    runs = 30
    hits = sum(experiment("learner", i)["gate1_improvement"]["passed"] for i in range(runs))
    assert hits / runs < 0.5, f"{hits}/{runs}: if this now passes, update the plan's power numbers"


def test_with_about_four_times_the_tasks_a_real_effect_is_detected_and_a_null_one_is_not(monkeypatch):
    """48 similar+transfer tasks: about 98% power and a few percent false alarms in the 60-run study (docs/EXPERIMENT-PLAN.md)."""
    with_more_tasks(monkeypatch, 4)
    runs = 12
    hits = sum(experiment("learner", i)["gate1_improvement"]["passed"] for i in range(runs))
    false_alarms = sum(experiment("null", i)["gate1_improvement"]["passed"] for i in range(runs))
    assert hits / runs >= 0.80, f"{hits}/{runs} detected"
    assert false_alarms / runs <= 0.25, f"{false_alarms}/{runs} false alarms"


def test_an_agent_hurt_by_memory_is_reported_as_hurt():
    runs = 30
    verdicts = [experiment("harmful", i, base=0.7)["gate1_improvement"]["verdict"] for i in range(runs)]
    assert verdicts.count("hurts") / runs >= 0.80, verdicts
    assert "improves" not in verdicts


def test_retention_gate_catches_forgetting_and_passes_when_nothing_is_lost():
    runs = 20
    forgot = [experiment("harmful", i, base=0.9, effect=0.5)["gate2_retention"] for i in range(runs)]
    assert sum(not g["passed"] for g in forgot) / runs >= 0.8 and all(g["mastered_tasks"] > 0 for g in forgot)
    kept = [experiment("learner", i, base=0.9)["gate2_retention"] for i in range(runs)]
    assert sum(g["passed"] for g in kept) / runs >= 0.9


def test_retention_gate_says_inconclusive_when_nothing_is_mastered():
    gate = experiment("learner", 0, base=0.3)["gate2_retention"]
    assert gate["inconclusive"] and not gate["passed"]


def test_auditability_gate_passes_for_normal_runs():
    assert experiment("learner", 0)["gate3_auditability"]["passed"]
