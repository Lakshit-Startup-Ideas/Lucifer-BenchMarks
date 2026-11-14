import numpy as np
import pytest

from lucv11.m3 import (AGENTS, CAPACITY, FULL, ROUTER, SCENARIOS, Agent, Scenario, WorkingMemory, make_episodes, run_agent)

PERFECT = Scenario("perfect", 1.0)
ALWAYS_BURST = Scenario("burst", 1.0, burst_p=1.0)


def test_fifo_memory_evicts_the_oldest_item_and_respects_capacity():
    wm = WorkingMemory(3, distractors_first=False)
    for i in range(5):
        wm.push(("s", i))
    assert list(wm.items) == [("s", 2), ("s", 3), ("s", 4)]


def test_priority_memory_evicts_distractors_before_goals():
    wm = WorkingMemory(3, distractors_first=True)
    wm.push(("s", 0)); wm.push(("d", 0)); wm.push(("s", 1))
    wm.push(("s", 2))
    assert ("d", 0) not in wm.items and ("s", 0) in wm.items
    wm2 = WorkingMemory(2, distractors_first=True)
    wm2.push(("s", 0)); wm2.push(("s", 1)); wm2.push(("s", 2))
    assert list(wm2.items) == [("s", 1), ("s", 2)]  # no distractor to evict: oldest goes


def test_memory_never_exceeds_capacity():
    wm = WorkingMemory(CAPACITY, distractors_first=True)
    for i in range(50):
        wm.push(("d" if i % 2 else "s", i))
        assert len(wm.items) <= CAPACITY


def test_router_forgets_subgoals_under_interruptions_but_executive_rebuilds_them():
    router = run_agent(ROUTER, ALWAYS_BURST, 0)
    full = run_agent(FULL, ALWAYS_BURST, 0, 1)
    assert router["completion"] < 0.2
    assert full["completion"] == 1.0 and full["control"] > 0  # rebuilds and monitor checks cost control steps


def test_monitor_retries_a_module_that_never_works_when_detection_is_perfect():
    class Broken(Scenario):  # the prior says every module is perfect (ties go to module 0), but module 0 never succeeds
        def reliability(self, episode):
            rel = np.ones((4, 4)); rel[0, :] = 0.0
            return rel
    broken = Broken("broken", 1.0)
    monitored = run_agent(FULL, broken, 0, detect=1.0, false_alarm=0.0)
    blind = run_agent(ROUTER, broken, 0)
    assert monitored["completion"] > 0.9 and blind["completion"] < 0.1


def test_calls_never_exceed_the_budget_and_router_has_zero_control_steps():
    scn = SCENARIOS["S1-failures"]
    out = run_agent(FULL, scn, 3)
    assert out["cost"] <= 2 * 5  # budget is 2k calls of cost 1.0, k <= 5
    assert run_agent(ROUTER, scn, 3)["control"] == 0


def test_learning_moves_estimates_toward_observed_outcomes():
    drift = SCENARIOS["S3-drift"]
    learned = run_agent(FULL, drift, 0)["completion_post"]
    static = run_agent(Agent("static", True, True, False, True), drift, 0)["completion_post"]
    assert learned > static


def test_cost_aware_choice_prefers_the_cheaper_module_when_reliability_is_close():
    cost_world = SCENARIOS["S5-cost"]
    cheap = run_agent(FULL, cost_world, 0)["cost"]
    pricey = run_agent(Agent("no-conflict", True, True, True, False), cost_world, 0, 1)["cost"]
    assert cheap < pricey


def test_same_seed_same_result_and_episodes_are_shared_across_agents():
    assert run_agent(FULL, SCENARIOS["S4-combined"], 2) == run_agent(FULL, SCENARIOS["S4-combined"], 2)
    assert make_episodes(SCENARIOS["S4-combined"], 5) == make_episodes(SCENARIOS["S4-combined"], 5)


def test_drift_changes_the_world_after_the_drift_point_only():
    drift = SCENARIOS["S3-drift"]
    assert np.array_equal(drift.reliability(0), drift.prior()) and not np.array_equal(drift.reliability(200), drift.prior())


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
def test_every_agent_runs_in_every_scenario_and_stays_in_range(agent):
    for scn in SCENARIOS.values():
        r = run_agent(agent, scn, 1)
        assert 0.0 <= r["completion"] <= 1.0 and r["cost"] >= 0 and r["control"] >= 0
