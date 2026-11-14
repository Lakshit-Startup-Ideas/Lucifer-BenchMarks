# M4 results: retrieval vs parameter adaptation vs protection

Run 1 (14 Nov 2026), 30 seeds, code commit `8364a99`, raw data `results/m4/run1.json`. Registered hypotheses: `M4-PREREGISTRATION.md`. Post-hoc checks: `results/m4/exploratory.json` (code `src/lucv11/m4_exploratory.py`).
A small simulated learner on a synthetic stream we authored. It says nothing about LLMs or the V1 result.

## Registered verdicts
| Hypothesis | Verdict | Evidence (mean, 95% interval, 30 paired seeds) |
|---|---|---|
| Precondition: `P` forgets >= 0.05 | met | forgetting of `P` = 0.159 |
| H4a adaptation is not retrieval | **FAIL** | (i) few-shot late, `P` minus `R`: +0.079 [+0.040, +0.118] (needed >= +0.10): missed. (ii) `P` few-shot late minus early: -0.003 [-0.054, +0.046] (needed >= +0.10): **no cross-context speed-up**. (iii) `R` late minus early: -0.010 [-0.056, +0.036]: inside +-0.03 only if the interval were narrower; counted as not met |
| H4b replay protects (100-slot buffer) | **FAIL** | forgetting `P` minus `P+replay` = **-0.023** [-0.031, -0.015]: replay made forgetting slightly *worse* |
| H4c anchor protects with no stored experience | **PASS** | forgetting `P` minus `P+anchor` = +0.138 [+0.131, +0.145]; final accuracy anchor minus `P` = -0.014 [-0.023, -0.006] (limit -0.03) |
| H4d cost reported | done | table below |
| H4e logging is not learning; unlearning needs retraining | **PASS** | 9 property tests in `tests/test_events.py`, all passing (list below) |

## Table (means over 30 seeds)
| Condition | Final accuracy | Forgetting | Few-shot early / late | Raw experiences kept |
|---|---|---|---|---|
| `R` retrieval | 0.711 | 0.000 (by construction) | 0.518 / 0.508 | 960 |
| `P` parameters | 0.752 | 0.159 | 0.590 / 0.587 | 0 |
| `P+replay` (100) | 0.714 | 0.182 | 0.600 / 0.621 | 100 |
| `P+anchor` | 0.738 | 0.021 | 0.592 / 0.574 | 0 |

## Post-hoc checks (run after seeing the failures; cannot change the verdicts above)
- **Is the replay code broken?** No. Forgetting reduction vs `P`, by buffer size: 100 slots **-0.023** [-0.031, -0.015]; 300 slots **+0.043** [+0.034, +0.051]; 960 slots (everything) **+0.060** [+0.051, +0.068]. The registered 100-slot buffer (about 10% of the stream) was too small; replay helps only with a large buffer, and even the full buffer leaves forgetting at 0.099, far above the anchor's 0.021.
- **Final accuracy, descriptive:** `P` minus `R` = +0.041 [+0.032, +0.049]; `P+anchor` minus `R` = +0.027 [+0.018, +0.036]. Parameter adaptation generalises a little better than 5-nearest-neighbour retrieval on this stream.

## H4e properties (tests, no statistics)
Logging an experience does not change parameters; experience and learning are separate ledger entries and the ledger never carries raw content; replaying the learning events from the initial checkpoint reproduces the live parameters exactly (hash equal); editing a stored experience, a ledger entry or a state transition is detected; deleting a raw record leaves the parameters unchanged and makes naive replay fail; rebuilding from the checkpoint with that record skipped gives parameters different from the live ones and identical to a run that never saw it.

## What this establishes
1. **Forgetting is real and measurable** in the parametric learner (0.159), and retrieval does not suffer it (but keeps every raw experience).
2. **A consolidation anchor removes most forgetting (0.159 to 0.021) with zero stored experiences**, for a small accuracy cost (-0.014). This matters because it needs no raw private data to be retained.
3. **Replay is not free**: it needs a large buffer (here 30% or more of the stream) to help, and it retains raw experiences, which collides with the project rule to keep raw private experience local and minimal.
4. **Logging, learning and unlearning can be separated and checked**: the pipeline reproduces training exactly, and removing an experience's influence requires retraining from a checkpoint; deleting the record alone does nothing to the parameters.

## What it does not establish
- **No cross-context benefit from adaptation was shown** (H4a): the learner did not get faster at new contexts as experience accumulated. Possible reasons (not tested): too few updates in the first 10 examples, the shared matrix drifting, the rank-4 bottleneck. Do not claim "experience makes the system learn faster" from this.
- Anything about language models, the V1 gain, or a hybrid of retrieval and parameters (untested).
- That the anchor strength (lambda 1.0) or the buffer sizes are good choices; they were fixed in advance and not tuned.

## Decision: ADR `decisions/0003-consolidation-anchor-and-event-sourced-learning.md`
