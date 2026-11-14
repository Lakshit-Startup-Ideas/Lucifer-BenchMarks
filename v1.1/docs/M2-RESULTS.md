# M2 results: does growing a recurrent network help?

Run 2 (14 Nov 2026), 20 seeds, code commit `c25ea4f`, raw data `results/m2/run2.json`. Hypotheses and the amendment that produced run 2: `M2-PREREGISTRATION.md`. Run 1 (uninformative, kept) is `results/m2/run1*`.
This is a simulation of 40 to 160-unit recurrent networks on a delay-recall toy task. It is not evidence about LLMs or about Lucifer V1.

## Verdicts against the pre-registered failure conditions
| Hypothesis | Verdict | Evidence (mean, 95% interval over 20 paired seeds) |
|---|---|---|
| H2a triangular growth keeps earlier tasks exactly | **PASS** | max change in NMSE 8e-17 (floating-point noise) |
| H2b rewiring growth forgets earlier tasks | **PASS** | earlier-task NMSE after growth: 195 and 86 (was 0.035 and 0.062); mean increase 141 [75, 219] |
| H2c triangular growth non-inferior to fixed-large on the last task | **FAIL** | NMSE 0.417 vs 0.068; difference +0.349 [+0.301, +0.404], limit was < +0.02 |
| H2d triangular growth cheaper than fixed-large | **FAIL** | unit-steps 1,932,000 vs 1,920,000; difference +12,000 [-48,000, +66,000] |
| H2e triangular growth better than fixed-small on the last task | PASS | NMSE 0.417 vs 0.598; difference -0.181 [-0.225, -0.140] |
| H2f importance pruning to 50% (refit head) | **FAIL** | vs unpruned +0.012 [+0.004, +0.022] (within 0.05, fine); vs random pruning -0.0003 [-0.011, +0.010] (not better than random) |

## Table (means over 20 seeds)
| Condition | Final units | Unit-steps | Params (nonzero) | NMSE after all tasks (delay 5 / 8 / 11) |
|---|---|---|---|---|
| fixed-small | 40 | 480,000 | 358 | 0.035 / 0.199 / 0.598 |
| fixed-large | 160 | 1,920,000 | 3,381 | 0.009 / 0.025 / 0.068 |
| grow-tri | 160 | 1,932,000 | 2,247 | 0.035 / 0.113 / 0.417 |
| grow-full | 154 | 1,710,000 | 2,969 | **195 / 86** / 0.115 |

## What this establishes
1. **Stability-plasticity is a real trade-off in growth design, measured.** Wiring new units so they cannot affect old ones protects earlier learning exactly (provable, and observed). Wiring them in both directions gives much better capacity (0.115 on the hardest task) but destroys every earlier readout (NMSE 195 and 86; heads were not refit, which is the continual-learning condition).
2. **Safe growth cost capacity.** At the same final size, triangular growth reaches NMSE 0.417 where a fixed network reaches 0.068. A likely reason (not tested): the old units cannot receive anything from the new ones, so the recurrent memory loop never gets larger; only a feed-forward side branch is added.
3. **No compute saving was found.** Growth re-runs the network after each growth step, and ended at the same size as the fixed-large network.
4. **Pruning by importance (|head weight| x state std) is no better than random** here, so that criterion is not worth building on.

## What it does not establish
- That growth is useless in general. Only one growth rule per variant, one growth trigger, one tiny task family, no replay and no head refitting after growth were tested. A fair rematch would give `grow-full` a way to keep old readouts working (replay, or readout refit on stored states) and would compare against a fixed-large network that is *also* continually trained.
- Anything about experience-driven adaptation, language models, or the V1 result.
- Whether the threshold (NMSE 0.10) and step (40 units) are good choices; they were fixed in advance and never tuned.

## Decision (see `decisions/0001-dynamic-topology-not-justified-yet.md`)
Dynamic topology is **not** adopted into the V1.1 architecture by default. The baseline for M3 onward is a fixed topology with parameter-level plasticity. Structural growth stays a documented option that must beat the matched fixed network in a new pre-registered test before it is used.
