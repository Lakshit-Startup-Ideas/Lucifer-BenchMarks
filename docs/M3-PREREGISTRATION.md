# M3 pre-registration: a hybrid executive subsystem (working memory, goals, monitoring, conflict resolution)

Written BEFORE any M3 code or run (14 Nov 2026). Amendments go at the bottom with the reason, as in M2.

## What this is, and the limit that matters most
A **mechanism validation in a designed simulation**, not evidence of reasoning ability. The environment and the executive are both written by us, so an executive that helps in an environment built to need it proves little. Two things keep it honest:
1. a **benign world** where the executive should NOT help (it must show no gain and a measurable overhead), and
2. a **double dissociation**: removing each component must hurt in the world built to need it and must NOT hurt in the benign world.
It also says nothing about LLMs or about the V1 retrieval result.

## Architecture under test (hybrid: deterministic control + learned estimates, no central bottleneck network)
- **Working memory (WM):** capacity 5 slots, holds pending subgoals and distractor items. Overflow eviction: baseline = FIFO; executive = distractors first, then oldest.
- **Goal slot (protected):** the executive stores the full plan outside WM. A subgoal missing from WM is rebuilt from the goal at cost 1 control step.
- **Monitor:** observes a failure signal (detects a true failure with prob 0.9, false alarm 0.05 on a success). On a detected failure it retries the subgoal with the best untried module until the episode's call budget (2 x plan length) is spent.
- **Learned estimates:** per (module, type) success estimate, exponentially weighted (alpha 0.1) from observed outcomes, initialised at the prior.
- **Conflict resolution:** choose the module with the highest `estimate - 0.1 * cost` (ablation: highest estimate only, ties by index).
- **Router (control):** static prior argmax, FIFO WM, no goal slot, no monitor (assumes every call succeeded), no learning, reliability-only choice.

## World (fixed)
4 task types, modules 0..3 are specialists (reliability 0.9 on their own type, 0.5 on others) except in S5. Episode = plan of k in 3..5 subgoals (see amendment A1) of random types; budget = 2k module calls; an episode is **completed** only if every subgoal truly succeeded. 300 episodes per seed, 30 seeds (0..29), the same plans/interruptions per seed for every agent (paired).

| Scenario | Change from the benign setup |
|---|---|
| S0 benign | every module reliability 0.97 on every type; no interruptions; no drift |
| S1 failures | specialists as above (0.9 / 0.5); no interruptions |
| S2 interruptions | reliability 0.97; before each subgoal, with prob 0.5 a burst of 3 distractor items enters WM |
| S3 drift | specialists; after episode 150 the specialist assignment rotates by one type (prior stays the pre-drift one) |
| S4 combined | specialists + interruptions + drift |
| S5 cost | one generalist module (reliability 0.85 on all types, cost 0.3) plus specialists (0.9 on own type, 0.5 else, cost 1.0); no interruptions, no drift |

Metrics: completion rate per seed; module cost units per episode; control steps per episode (every rebuild, every monitor check = 1).
Statistics: paired difference over 30 seeds, 95% bootstrap interval, 10,000 resamples.

## Hypotheses and failure conditions
- **H3a (benefit where needed).** S4: executive-full minus router completion >= +0.15 with the lower end of the interval > +0.10. FAILS otherwise.
- **H3b (no free lunch).** S0: |executive-full minus router completion| < 0.02 (interval inside +-0.02) AND executive-full control steps per episode > router's. FAILS if either part is false.
- **H3c (double dissociation).** On-target drops (executive-full minus ablation, completion): `-goal` in S2 >= 0.10; `-monitor` in S1 >= 0.10; `-learning` in S3 >= 0.10 (measured on episodes after the drift); `-conflict` in S5: cost units per episode higher by >= 0.5 with completion drop <= 0.03. Off-target: each ablation's completion drop in S0 < 0.02. FAILS if any on-target threshold is missed or any off-target drop is >= 0.02.
- **H3d (overhead is reported, not hidden).** Control steps per episode are reported for every agent in every scenario (no threshold).

## What a pass would and would not mean
A pass shows the four mechanisms behave as specified, each separable and each useful only where its world needs it. It does not show planning, reasoning or generalisation. A failure of H3b would mean the executive helps for reasons unrelated to need (a bug or an unfair control). Next dependency after M3: a version where the environment is not authored by us (tool-use or planning tasks from the V1 task bank) and a language model is the worker.

## Amendments

**A1 (14 Nov 2026, before any code or run): plan length 3..6 -> 3..5.** A plan of 6 subgoals does not fit the 5-slot working memory at the start, so the router would fail every such episode even in the benign world, which would make H3b untestable and unfair to the control. No result had been seen. Also fixed before running (not a threshold change): (i) retries may only use calls beyond one reserved call per remaining subgoal; (ii) observations (and therefore learning) exist only when the monitor is on, so `-monitor` also silences learning (a coupled ablation, reported as such).
