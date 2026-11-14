import dataclasses
import json

import numpy as np
import pytest

from lucv11.events import EventSourcedLearner, content_hash
from lucv11.learner import D, ParamModel


def build(seed=0, n=30, replay=True):
    rng = np.random.default_rng(seed)
    w = rng.normal(size=D)
    learner = EventSourcedLearner(seed)
    ids = []
    for i in range(n):
        x = rng.normal(size=D)
        ids.append(learner.observe(i % 3, x, int(x @ w > 0)))
    for k in range(0, n, 5):
        batch = ids[k:k + 5]
        learner.learn(batch, replay_ids=ids[:k][-3:] if replay and k else [])
    return learner, ids


def test_logging_an_experience_does_not_change_parameters():
    learner = EventSourcedLearner(1)
    before = learner.model.params_hash()
    learner.observe(0, np.ones(D), 1)
    assert learner.model.params_hash() == before and len(learner.learning) == 0


def test_experience_and_learning_are_separate_records_with_hashes():
    learner, ids = build()
    kinds = [e.kind for e in learner.ledger.entries]
    assert kinds.count("experience") == 30 and kinds.count("learning") == 6 and kinds[0] == "checkpoint"
    event = json.loads(next(e.text for e in learner.ledger.entries if e.kind == "learning"))
    assert event["exp_ids"] and event["before"] != event["after"] and len(event["after"]) == 64
    exp = json.loads(next(e.text for e in learner.ledger.entries if e.kind == "experience"))
    assert "x" not in exp and "content_sha256" in exp  # the ledger never carries the raw content


def test_replay_from_the_initial_checkpoint_reproduces_live_parameters_exactly():
    learner, _ = build()
    assert learner.rebuild("init").params_hash() == learner.model.params_hash()
    assert learner.verify()


def test_editing_a_stored_experience_is_detected():
    learner, ids = build()
    ctx, x, y = learner.store[ids[3]]
    learner.store[ids[3]] = (ctx, x + 1e-9, y)
    assert not learner.verify()


def test_editing_a_ledger_entry_is_detected():
    learner, _ = build()
    learner.ledger.entries[4] = dataclasses.replace(learner.ledger.entries[4], run_id="FORGED")
    assert not learner.verify()


def test_a_broken_state_transition_is_detected():
    learner, _ = build()
    learner.learning[2] = {**learner.learning[2], "before": "0" * 64}
    assert not learner.verify()


def test_deleting_a_record_does_not_change_parameters_and_breaks_naive_replay():
    learner, ids = build()
    live = learner.model.params_hash()
    victim = ids[7]
    del learner.store[victim]
    assert learner.model.params_hash() == live  # the influence stays in the parameters
    with pytest.raises(KeyError):
        learner.rebuild("init")


def test_unlearning_by_retraining_equals_a_run_that_never_saw_the_record():
    learner, ids = build()
    victim = ids[7]
    unlearned = learner.rebuild("init", skip=frozenset({victim}))
    assert unlearned.params_hash() != learner.model.params_hash()
    independent = ParamModel(0)
    for ev in learner.learning:
        for ident in [i for i in ev["exp_ids"] + ev["replay_ids"] if i != victim]:
            ctx, x, y = learner.store[ident]
            independent.step(ctx, x, float(y), ev["lr"])
    assert unlearned.params_hash() == independent.params_hash()


def test_content_hash_is_sensitive_to_every_field():
    x = np.arange(D, dtype=float)
    base = content_hash(1, x, 1)
    assert len({base, content_hash(2, x, 1), content_hash(1, x + 1e-12, 1), content_hash(1, x, 0)}) == 4
