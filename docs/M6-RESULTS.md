# M6 results: knowledge review, promotion, rollback and cross-child transfer

Code commit `809cc4a`; run 1 (14 Nov 2026), 30 seeds x 12 packages (6 honest, 6 poisoned per seed), raw data `results/m6/run1.json`. Registered hypotheses: `M6-PREREGISTRATION.md`.
Simulated, in-process, synthetic rules and a **non-adaptive** attacker. It says nothing about LLMs, real users or a deployed system.

## Registered verdicts
| Hypothesis | Verdict | Evidence |
|---|---|---|
| H6a hybrid blocks poison; metadata-only must fail | **PASS** | poisoned packages accepted: accept-all 1.00, **deterministic 1.00** (the metadata checks stopped none), hybrid **0.00** (0 of 180) |
| H6b hybrid lets agreeing knowledge through (>= 0.80) | **FAIL** | honest shared-rule packages accepted by hybrid: 0.722 [0.633, 0.811]; deterministic and accept-all 1.00 |
| H6c tenant-specific knowledge not promoted as shared (<= 0.10) | **PASS** | hybrid acceptance of honest tenant-specific packages 0.00 (0 of 180) |
| H6d cross-child transfer | **PASS** | tenant B accuracy, reviewed minus local-only: shared contexts **+0.109** [+0.092, +0.125]; tenant-specific contexts 0.000 [0.000, 0.000] (nothing adopted, so identical) |
| H6e versioning, rollback, tamper evidence, rejection reasons | **PASS** | 23 tests in `tests/test_knowledge.py` (list below) |
| H6f cost | reported | 4 evaluation messages per package (2 peers x 2 numbers); every package needed the peer step because every package passed the metadata checks |

Blind arm (accept-all promotion, B adopts the latest promoted package per context, no local test), minus local-only: shared contexts **-0.103** [-0.159, -0.049]; tenant-specific contexts **-0.146** [-0.168, -0.124]. Poison arrives in half the packages here, so this exaggerates a real network, but it shows the size of the harm when nothing reviews.

Acceptance by category (hybrid): honest-shared 0.722, honest-specific 0.000, poison-flip 0.000, poison-random 0.000, poison-blend 0.000.

## H6e properties (tests)
Promotion is a versioned ledger entry carrying the package, its provenance and the peers' numbers; rollback to version n restores exactly the earlier active set (state hash equal), keeps the archived promotions in the log, and version ids are never reused; editing or deleting a log entry is detected; unknown rollback target refused; each deterministic reason fires (no consent, unrecorded checkpoint, hash mismatch, anchor mismatch, revoked or unknown origin, rewritten origin history, bad length, non-finite values, wrong norm); a conflicting package needs a peer gain of 0.10 instead of 0.05; one unconvinced peer, or no evidence, blocks; peers' validation data does not appear in the parent's exported state.
**Do the tests bite?** 8 mutants (peer margin ignored; "any peer" instead of "all"; empty evidence accepted; consent unchecked; origin audit skipped; rollback keeping later versions; conflict margin ignored; anchor check skipped), each run from a copy with the tests beside it: all 8 killed.

## What this establishes
1. **Valid metadata is not evidence of benefit.** A poisoned package with a real checkpoint, consent and a unit-norm rule passes every deterministic check (tested directly and in 180 packages). Only evaluation on data the sender did not control separated good from bad.
2. **Private-data peer review works in this setting**: peers share two numbers per package, never data, and the hybrid reviewer blocked all 180 poisoned and all 180 tenant-specific packages while the poor tenant gained +0.109 on the contexts where knowledge agreed.
3. **Caution has a price**: 28% of honest useful packages were also rejected, mostly because unanimity among peers plus a 0.05 margin is strict when validation sets have 200 items.
4. Promotion is auditable and reversible: a promoted package found harmful later can be rolled back to the exact earlier state.

## What it does not establish
- **Resistance to a smart attacker.** A package crafted to score well on the peers' validation data, or colluding peers, were not tested. The poison here was fixed in advance (flip, random, blend).
- **Zero risk.** "0 of 180" bounds the true acceptance rate only up to about 1.7% (rule of three, 95%); the bootstrap interval [0, 0] understates that.
- **Privacy of the packages.** A rule vector can leak information about the data it was learned from (membership inference). No clipping or noise was applied; this is open and needs its own test before any real sharing.
- Reproducibility of a package from raw data (the parent cannot rebuild it); the independent-model and neural reviewers (not built); anything about LLMs.
- Whether majority voting, a lower margin or larger validation sets fix the 28% false rejection without admitting poison (untested).

## Decision: ADR `decisions/0005-hybrid-review-with-peer-evaluation.md`
