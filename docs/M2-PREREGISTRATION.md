# M2 pre-registration: dynamic topology in a minimal recurrent network

Written BEFORE the experiment was run (14 Nov 2026). Thresholds are not changed after seeing results; if one is changed it is logged in the "Amendments" section at the bottom with the reason.

Scope warning: this is a **simulation of small recurrent networks**. It says nothing about LLMs, and nothing about Lucifer V1's retrieval result. It tests one narrow question: does growing a network's topology help compared with a fixed network of the same final size, and what does growth do to earlier learning?

## Setup (fixed)
- Network: leaky echo-state recurrent net, `h' = (1-a)h + a*tanh(W h + Win u + b)`, leak a = 0.3, spectral radius of `W` set to 0.95, density 0.1. Readout: one linear head per task, ridge regression (lambda 1e-4), heads are never refit after their task.
- Tasks (task-incremental): K = 3 delay-recall tasks, target `y[t] = u[t-d]`, delays d = 5, 15, 30, input uniform(-0.5, 0.5), 2000 training steps (25% held out for the growth decision), 1000 test steps, washout 100. Same data for every condition within a seed.
- Seeds: 20 (0..19). Paired comparison across seeds, 95% bootstrap interval (10,000 resamples) on the paired difference.
- Metric: normalised MSE (NMSE = MSE / variance of the target). Lower is better.
- Cost proxy: **unit-steps** = sum over every simulated time step (training + validation + tests) of the number of units at that moment.

## Conditions
| Name | Description |
|---|---|
| `fixed-small` | 40 units, never changes |
| `fixed-large` | 160 units, never changes (matches the final size of the growing nets) |
| `grow-tri` | starts at 40; after fitting the head for a task, if held-out NMSE > 0.10 and n < 160, add 40 units and refit that head. New units receive from old units and input but send nothing back (block lower-triangular `W`) |
| `grow-full` | same trigger; new units are wired both ways and the whole `W` is rescaled to spectral radius 0.95 |

## Hypotheses (each with its failure condition)
- **H2a (exact retention).** In `grow-tri`, earlier tasks' NMSE after later growth equals their NMSE before growth: max abs change < 1e-9 across all seeds and tasks. Mathematical reason: a block-triangular `W` leaves the old units' dynamics unchanged and the old heads ignore the new units. FAILS if any change >= 1e-9 (that would be a bug, not a result).
- **H2b (full rewiring forgets).** In `grow-full`, the mean increase in NMSE of earlier tasks after later growth is > 0.05. FAILS if <= 0.05 (then rewiring growth is harmless here and the triangular design is not needed).
- **H2c (non-inferior to fixed-large).** `grow-tri` final-task (delay 30) NMSE is not worse than `fixed-large` by more than 0.02 (upper end of the 95% interval of the paired difference < 0.02). FAILS otherwise.
- **H2d (cost).** `grow-tri` uses fewer unit-steps than `fixed-large` (paired interval entirely below 0). FAILS otherwise.
- **H2e (growth helps vs small).** `grow-tri` has lower NMSE than `fixed-small` on the delay-30 task (interval below 0). FAILS otherwise.
- **H2f (pruning).** Single task (delay 15), 160 units trained, then prune to 80 by importance (`|head weight| x state std`) and refit the head. NMSE after pruning is within 0.05 of before, and better than random pruning (paired interval below 0). FAILS otherwise.

## What a pass would and would not mean
A pass on H2c+H2d says growth saved compute in this toy setting at no accuracy loss. It does not show a computational advantage that carries over to language models, nor "experience-driven" adaptation. A failure of H2c or H2d means dynamic topology is **not** justified by this evidence, and it stays out of the architecture until a better test says otherwise.

## Amendments
(none)
