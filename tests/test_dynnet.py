import numpy as np
import pytest

from lucv11.dynnet import Head, Reservoir, nmse, spectral_radius
from lucv11.m2 import DELAYS, N_START, make_task, paired_ci, prune_experiment, run_condition


def test_initial_spectral_radius_is_rho():
    assert spectral_radius(Reservoir(60, rho=0.9, seed=1).W) == pytest.approx(0.9)


def test_triangular_growth_keeps_old_states_exactly_and_radius_bounded():
    net = Reservoir(40, seed=2)
    u = np.random.default_rng(0).uniform(-0.5, 0.5, (300, 1))
    before = net.run(u)
    net.grow(40, "tri")
    after = net.run(u)
    assert net.n == 80
    # Old units cannot hear the new ones. Not bit-identical: BLAS sums an 80x80 product in a different order (measured diff 1.7e-16).
    assert np.allclose(after[:, :40], before, rtol=0, atol=1e-12)
    assert spectral_radius(net.W) <= net.rho + 1e-9


def test_full_growth_changes_old_states_but_keeps_radius():
    net = Reservoir(40, seed=2)
    u = np.random.default_rng(0).uniform(-0.5, 0.5, (300, 1))
    before = net.run(u)
    net.grow(40, "full")
    assert not np.allclose(net.run(u)[:, :40], before)
    assert spectral_radius(net.W) == pytest.approx(net.rho)


def test_unknown_growth_mode_is_rejected():
    with pytest.raises(ValueError):
        Reservoir(10, seed=0).grow(5, "sideways")


def test_state_stays_bounded_for_a_long_run():
    net = Reservoir(60, seed=3)
    s = net.run(np.random.default_rng(1).uniform(-0.5, 0.5, (5000, 1)))
    assert np.all(np.abs(s) <= 1.0) and np.all(np.isfinite(s))


def test_prune_keeps_requested_units_and_radius():
    net = Reservoir(60, seed=4)
    win_old = net.Win.copy()
    net.keep(np.array([5, 1, 30, 7]))
    assert net.n == 4
    assert np.array_equal(net.Win, win_old[[1, 5, 7, 30]])  # kept units are the requested ones, in sorted order
    assert spectral_radius(net.W) <= net.rho + 1e-9


def test_head_recovers_a_known_linear_map():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((500, 6))
    w = rng.standard_normal(6)
    y = x @ w + 0.7
    assert nmse(Head.fit(x, y, ridge=1e-9).predict(x), y) < 1e-9


def test_head_ignores_units_added_after_it_was_fitted():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((200, 5))
    head = Head.fit(x, x[:, 0])
    wide = np.hstack([x, rng.standard_normal((200, 3))])
    assert np.array_equal(head.predict(x), head.predict(wide))


def test_nmse_reference_points():
    y = np.random.default_rng(0).standard_normal(1000)
    assert nmse(y, y) == 0.0
    assert nmse(np.full_like(y, y.mean()), y) == pytest.approx(1.0)


def test_task_target_is_the_delayed_input():
    task = make_task(7, seed=5)
    u, y = task["train"]
    assert np.array_equal(y[7:], u[:-7, 0])


def test_same_seed_gives_the_same_result():
    a, b = run_condition("grow-tri", 3), run_condition("grow-tri", 3)
    assert a.nmse_final == b.nmse_final and a.unit_steps == b.unit_steps


def test_fixed_conditions_never_change_size_and_tri_never_forgets():
    small = run_condition("fixed-small", 0)
    assert small.units == N_START
    tri = run_condition("grow-tri", 0)
    assert max(abs(f - a) for f, a in zip(tri.nmse_final, tri.nmse_after_training)) < 1e-9
    assert len(tri.nmse_final) == len(DELAYS)


def test_prune_experiment_returns_all_arms():
    assert set(prune_experiment(0)) == {"full", "importance", "random"}


def test_paired_ci_contains_the_mean_and_is_ordered():
    m, lo, hi = paired_ci(np.array([1.0, 2.0, 3.0, 4.0]))
    assert lo <= m <= hi
