# M3 results: hybrid executive mechanisms

Run 1 (14 Nov 2026), 30 seeds x 300 episodes, code commit `33fff04`, raw data `results/m3/run1.json`. Registered hypotheses: `M3-PREREGISTRATION.md`. Post-hoc check: `results/m3/exploratory-X0.json` (code `src/lucv11/m3_exploratory.py`).
This is a mechanism validation in a world we designed. The size of every effect below follows from our parameters (for example, an interruption burst of 3 items into a 5-slot memory) and is **not an estimate of anything real**. It says nothing about LLMs or the V1 result.

## Registered verdicts
| Hypothesis | Verdict | Evidence (mean, 95% interval, 30 paired seeds) |
|---|---|---|
| H3a benefit where needed (S4) | **PASS** | executive-full minus router completion +0.794 [+0.786, +0.802] (needed >= +0.15, lower end > +0.10) |
| H3b no free lunch (S0) | **FAIL** | completion +0.104 [+0.098, +0.111] (needed within +-0.02); control steps 4.32 vs 0 (that part held) |
| H3c double dissociation | **FAIL** (2 of 8 checks) | see below |
| H3d overhead reported | done | table below |

H3c detail (executive-full minus ablation):
| Check | Needed | Observed | |
|---|---|---|---|
| `-goal` in S2 (interruptions) completion drop | >= 0.10 | +0.768 [+0.760, +0.776] | pass |
| `-monitor` in S1 (failures) completion drop | >= 0.10 | +0.238 [+0.227, +0.250] | pass |
| `-learning` in S3 (drift, post-drift episodes) completion drop | >= 0.10 | +0.278 [+0.260, +0.296] | pass |
| `-conflict` in S5: cost units saved per episode | >= 0.5 | +0.405 [+0.294, +0.517] | **fail** (threshold missed; completion change -0.006, within the 0.03 limit) |
| Off-target in S0: `-goal` / `-learning` / `-conflict` completion drop | < 0.02 | +0.002 / +0.001 / -0.001 | pass |
| Off-target in S0: `-monitor` completion drop | < 0.02 | **+0.104** [+0.099, +0.110] | **fail** |

## Why H3b and the `-monitor` off-target check failed
My "benign" world was not benign: each call still failed 3% of the time, so a monitor that retries helps (router 0.884 vs executive 0.989). The registered expectation was wrong, not (as far as the evidence shows) the code.
Check, run **after** seeing the failure (post-hoc, exploratory, cannot change the verdicts): a world where nothing can fail (reliability 1.0): completion gain is exactly 0.0 for every component; the executive still spends **4.21 control steps per episode**, and false alarms cause **+0.21 extra module cost** per episode (4.21 vs 4.00). So the "no free lunch" property does hold once the world really is failure-free.

## Table (means over 30 seeds; completion / module cost units / control steps per episode)
| Scenario | router | exec-full | -goal | -monitor | -learning | -conflict |
|---|---|---|---|---|---|---|
| S0 benign (3% fail) | 0.884 / 4.00 / 0 | 0.989 / 4.32 / 4.32 | 0.986 / 4.33 / 4.33 | 0.884 / 4.00 / 0 | 0.987 / 4.34 / 4.34 | 0.990 / 4.33 / 4.33 |
| S1 failures | 0.653 / 4.00 / 0 | 0.895 / 4.91 / 4.91 | 0.888 / 4.92 / 4.92 | 0.657 / 4.00 / 0 | 0.893 / 4.91 / 4.91 | 0.893 / 4.91 / 4.91 |
| S2 interruptions | 0.199 / 1.57 / 0 | 0.989 / 4.32 / 4.49 | 0.221 / 1.71 / 1.71 | 0.884 / 4.00 / 0.17 | 0.987 / 4.34 / 4.50 | 0.990 / 4.33 / 4.50 |
| S3 drift (post-drift completion) | 0.074 | 0.864 | 0.851 | 0.068 | 0.585 | 0.863 |
| S4 combined | 0.086 / 1.57 / 0 | 0.880 / 5.03 / 5.19 | 0.191 / 2.04 / 2.04 | 0.361 / 4.00 / 0.17 | 0.736 / 5.77 / 5.93 | 0.879 / 5.00 / 5.16 |
| S5 cost | 0.653 / 4.00 / 0 | 0.932 / 3.13 / 4.78 | 0.929 / 3.17 / 4.79 | 0.521 / 1.20 / 0 | 0.921 / 2.06 / 4.86 | 0.938 / 3.54 / 4.76 |

## What this establishes (and only this)
1. The four mechanisms are **separable**: each one's removal hurts in the world that needs it (protected goal slot under interruptions, monitor under failures, learned estimates under drift) and barely matters elsewhere.
2. Protecting goals from eviction is the largest effect here (+0.77 under interruptions); it is also the most parameter-dependent.
3. **Overhead is real**: 4 to 6 control steps per episode, plus extra module cost from retries and false alarms, even when nothing was needed.
4. Cost-aware choice saves about 0.4 cost units per episode at no measurable completion loss, below the 0.5 I registered.
5. `-monitor` is a coupled ablation (no observations means no learning), so its S3/S4 drop mixes two components.

## What it does not establish
Planning, reasoning, generalisation, or that a learned executive network is needed or unnecessary. No non-authored task was used, and no language model.

## Decision: ADR `decisions/0002-executive-as-separable-components.md`
