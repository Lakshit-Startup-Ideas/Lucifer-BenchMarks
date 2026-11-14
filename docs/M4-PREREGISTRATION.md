# M4 pre-registration: experience-driven learning, retention and forgetting

Written BEFORE any M4 code or run (14 Nov 2026). Amendments go at the bottom with the reason, as in M2 and M3.

## The question V1 could not answer
V1's gain is consistent with "the model reads a hint". M4 separates three things on one stream of experience:
1. **Retrieval** (store experiences, look the nearest up),
2. **Parameter adaptation** (a shared model updated by feedback),
3. **Protection** (keeping old learning while learning new things: replay, or a consolidation anchor).
Scope limit: a **small simulated learner on a synthetic stream**. It says nothing about LLMs or the V1 result, and the world is authored by us.

## World (fixed)
- Items `x ~ N(0, I_20)`; binary label `y = [w_c . x > 0]` for context `c`. 12 contexts shown **in sequence** (one phase each, 80 labelled examples per phase, online: predict, then learn). After every phase, accuracy is measured on 300 fresh test items for every context seen so far.
- Contexts share structure and also differ: `w_c = 0.5 g + 0.5 s_c` (then normalised), `g` a fixed unit direction per seed, `s_c` a random sparse vector (3 active coordinates, +-1).
- 30 seeds (0..29), paired across conditions (same world per seed).

## Conditions
| Name | What it keeps | Update rule |
|---|---|---|
| `R` retrieval | every experience, per context | none; predict by 5-nearest-neighbours inside the context; random guess if the context has no examples |
| `P` parameters | no raw experience | shared matrix `U` (20x4) and a head `v_c` (4) per context, `logit = v_c . U^T x`; logistic-loss SGD, lr 0.1, one step per example, then 5 extra epochs over the current phase's 80 examples |
| `P+replay` | a reservoir of 100 past raw experiences | as `P`, plus a replay mini-batch of 8 from the reservoir at every step |
| `P+anchor` | a parameter snapshot, no raw experience | as `P`, plus an L2 pull of `U` toward its snapshot from the end of the previous phase, lambda 1.0 |

## Metrics
- **final accuracy**: mean over all 12 contexts after the last phase.
- **forgetting**: mean over contexts 1..11 of (best accuracy ever reached on that context minus its final accuracy).
- **few-shot accuracy**: online accuracy on the first 10 examples of a context's phase (before many updates). "Early" = contexts 1-3, "late" = contexts 9-12.
- storage: number of raw experiences kept at the end.
Statistics: paired difference over 30 seeds, 95% bootstrap interval (10,000 resamples).

## Precondition (decides whether H4b and H4c may be evaluated at all)
`P` must show forgetting >= 0.05 (mean). If not, the world has no interference to protect against; H4b and H4c are then reported as **not testable** and the world is amended openly (as in M2), calibrated only on `P`, never on the protective conditions.

## Hypotheses and failure conditions
- **H4a (adaptation is not retrieval).** (i) `P` few-shot (late) minus `R` few-shot (late) >= +0.10 with the lower end > +0.05; (ii) `P` few-shot late minus early >= +0.10 with the lower end > +0.05; (iii) `R` few-shot late minus early within +-0.03 (interval inside). FAILS if any part fails.
- **H4b (replay protects).** forgetting(`P`) minus forgetting(`P+replay`) >= 0.05 with the lower end > 0. FAILS otherwise.
- **H4c (anchor protects without storing experiences).** forgetting(`P`) minus forgetting(`P+anchor`) >= 0.05 with the lower end > 0, AND final accuracy of `P+anchor` >= final accuracy of `P` minus 0.03. FAILS otherwise.
- **H4d (cost is reported).** Storage and final accuracy are reported for all four conditions (no threshold). Replay keeps raw experiences; the project rule is that raw private experiences stay local and are not shared by default, so replay is local-only by design.
- **H4e (logging is not learning; unlearning needs retraining).** Property tests on the event pipeline, no statistics: (i) experience events and learning events are separate ledger entries, a learning event references experience ids and the parameter hash before and after; (ii) replaying the learning events from the initial checkpoint reproduces the live parameters exactly (hash equal); (iii) editing a stored experience or a ledger entry is detected by `verify()`; (iv) deleting an experience record does **not** change the live parameters, but replaying from the checkpoint without it gives parameters different from the live ones and identical to a run that never saw it. FAILS if any property fails.

## What a pass would and would not mean
A pass shows that parameter updates give something retrieval does not (benefit across contexts), that forgetting is real and measurable in this setting, and that two protection mechanisms work, one at the price of storing raw experience. It does not show that an LLM behaves this way, that these numbers carry over, or anything about consciousness or general intelligence.

## Amendments
(none)
