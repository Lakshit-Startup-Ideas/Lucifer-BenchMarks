import pytest

from lucv11 import m4
from lucv11.m8 import lam_constant, lam_mature, lr_constant, lr_mature, run_families, run_schedule


def test_schedules_have_the_registered_endpoints_and_are_monotone():
    assert lr_mature(0) == pytest.approx(0.2) and lr_mature(11) == pytest.approx(0.05)
    assert lam_mature(0) == pytest.approx(0.5) and lam_mature(11) == pytest.approx(2.0)
    assert all(lr_mature(t) > lr_mature(t + 1) and lam_mature(t) < lam_mature(t + 1) for t in range(11))
    assert lr_constant(5) == 0.1 and lam_constant(5) == 1.0


def test_the_anchor_control_reproduces_m4_p_plus_anchor_exactly():
    for seed in (0, 3):
        mine, ref = run_schedule(seed, lr_constant, lam_constant), m4.run_condition("P+anchor", seed)
        assert mine["final_acc"] == pytest.approx(ref["final_acc"], abs=1e-12) and mine["forgetting"] == pytest.approx(ref["forgetting"], abs=1e-12)


def test_a_different_schedule_gives_a_different_result():
    assert run_schedule(1, lr_mature, lam_mature) != run_schedule(1, lr_constant, lam_constant)


def test_family_experiment_is_deterministic_and_measuring_does_not_change_the_model():
    a, b = run_families(2), run_families(2)  # run_families asserts internally that the experienced model's hash is unchanged
    assert a == b and set(a) == {"same", "unseen"} and set(a["same"]) == {"experienced", "fresh"}


def test_accuracies_are_valid_fractions():
    r = run_families(0)
    assert all(0.0 <= v <= 1.0 for g in r.values() for v in g.values())
