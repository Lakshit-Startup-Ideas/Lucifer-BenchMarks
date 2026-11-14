import numpy as np

from lucv11.learner import D, ParamModel, sigmoid
from lucv11.m4 import CONDITIONS, CONTEXTS, PER_PHASE, knn_predict, make_world, run_condition


def test_world_is_deterministic_and_labels_follow_a_linear_rule():
    a, b = make_world(3), make_world(3)
    assert all(np.array_equal(x[0], y[0]) for x, y in zip(a["train"], b["train"]))
    X, Y = a["train"][0]
    assert set(np.unique(Y)) <= {0.0, 1.0} and 0.2 < Y.mean() < 0.8


def test_one_sgd_step_lowers_the_loss_on_that_example():
    rng = np.random.default_rng(0)
    m, x = ParamModel(0), rng.normal(size=D)
    loss = lambda: float(-np.log(sigmoid(m.logit(0, x))))  # label 1
    before = loss()
    m.step(0, x, 1.0, 0.1)
    assert loss() < before


def test_heads_are_deterministic_whatever_the_creation_order():
    a, b = ParamModel(5), ParamModel(5)
    a.head(1); a.head(2)
    b.head(2); b.head(1)
    assert np.array_equal(a.head(1), b.head(1)) and a.params_hash() == b.params_hash()


def test_a_single_context_is_learned_well_above_chance():
    w = make_world(0)
    m = ParamModel(0)
    X, Y = w["train"][0]
    for _ in range(6):
        for i in range(PER_PHASE):
            m.step(0, X[i], Y[i], 0.1)
    Xt, Yt = w["test"][0]
    assert np.mean((m.logit(0, Xt) > 0) == Yt) > 0.8


def test_anchor_pulls_the_shared_matrix_back_when_the_data_gradient_is_zero():
    m = ParamModel(0)
    m.U_anchor, m.anchor_lambda = m.U + 1.0, 1.0
    gap = np.linalg.norm(m.U - m.U_anchor)
    m.step(0, np.zeros(D), 0.0, 0.1)  # x = 0 gives zero data gradient
    assert np.linalg.norm(m.U - m.U_anchor) < gap


def test_knn_votes_and_handles_an_empty_store():
    rng = np.random.default_rng(0)
    xs = [np.zeros(D) + i for i in range(6)]
    assert knn_predict(xs, [1, 1, 1, 0, 0, 0], np.zeros(D), rng) == 1.0
    assert knn_predict([], [], np.zeros(D), rng) in (0.0, 1.0)


def test_retrieval_never_forgets_by_construction_and_stores_everything():
    r = run_condition("R", 1)
    assert r["forgetting"] == 0.0 and r["storage"] == CONTEXTS * PER_PHASE


def test_storage_accounting_and_determinism_per_condition():
    for cond in CONDITIONS:
        a, b = run_condition(cond, 2), run_condition(cond, 2)
        assert a == b
    assert run_condition("P", 2)["storage"] == 0 and run_condition("P+anchor", 2)["storage"] == 0
    assert run_condition("P+replay", 2)["storage"] == 100
