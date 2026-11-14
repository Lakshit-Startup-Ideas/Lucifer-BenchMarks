# M6 pre-registration: knowledge review, promotion, versioning, rollback and cross-child transfer

Written BEFORE any M6 code or run (14 Nov 2026). Amendments go at the bottom with the reason.

## Scope and limits
Builds on M5 (parent, children, metadata-only protocol) and M4 (learner). Simulated, in-process, synthetic rules authored by us. It says nothing about LLMs, real users or a deployed system.
A **knowledge package** = the decision rule one child learned for one context (`w = U v_c`, normalised to unit length), plus provenance (the checkpoint it came from) and a consent flag. Nothing else leaves the child. Packages are not raw data, but a rule vector can still leak information about the training data (membership inference); no noise or clipping is applied here, and that risk is listed as **not addressed**.

## Review mechanisms compared
| Reviewer | What it does | Location |
|---|---|---|
| `accept-all` | promotes every package | baseline |
| `deterministic` | consent given; origin registered and active; the package's checkpoint is one the parent recorded, with the same parameter hash and ledger anchor; the origin's history passes the anchored audit; the rule is finite, the right length and unit norm | parent |
| `hybrid` (the proposal) | `deterministic`, then **peer evaluation**: every other participating child scores the package and its own local model on its own private validation data and reports only the two numbers as evaluation messages through the M5 protocol; promote only if **every** peer's accuracy with the package beats its local accuracy by >= 0.05 | parent + peers (data never leaves a peer) |
| neural / independent-model reviewer | **not built.** No honest training data for a learned reviewer exists yet without circularity; deferred, not rejected | n/a |

Conflict rule: if the knowledge base already holds an active package for that context with cosine similarity < 0.3 to the new one, the new package needs peer gain >= 0.10 instead of 0.05.
Versioning: promotions are entries on a Ledger v2 chain with ever-increasing version ids; rollback to version n archives (never deletes) later promotions and is itself a ledger entry; the active set is recomputed by replaying entries.

## World (fixed)
3 tenants (A rich, B and C poor), 6 contexts, `x ~ N(0, I_20)`, hidden linear rules built as in M4/M5. Contexts 0-2 have the **same** rule in all tenants; contexts 3-5 are **tenant-specific** (independent rules). Training examples per context: A 60, B and C 12 (single pass plus 5 epochs, the M4 learner). Private validation set per tenant and context: 200 items; test set 300.
A exports one honest package per context. A compromised child `M` exports one **poisoned** package per context with valid metadata: kind drawn uniformly from {sign flip of the honest rule, random unit vector, blend `normalise(-0.5 w + 0.5 r)`}. Arrival order of packages is random per seed. 30 seeds, paired.
Peers evaluating A's and M's packages: B and C.

## Hypotheses and failure conditions
- **H6a (hybrid blocks poison; baseline must fail).** Acceptance rate of poisoned packages (over contexts and seeds): `hybrid` <= 0.05 with the upper end of the 95% interval < 0.10; AND `deterministic` >= 0.90 (if metadata checks already block the poison, the peer step is not justified). FAILS if either part fails.
- **H6b (hybrid lets useful knowledge through).** Honest packages for contexts 0-2 (same rule everywhere): `hybrid` acceptance >= 0.80.
- **H6c (hybrid does not promote tenant-specific knowledge as shared).** Honest packages for contexts 3-5: `hybrid` acceptance <= 0.10.
- **H6d (cross-child transfer).** Tenant B's test accuracy, `reviewed` (hybrid promotion, then B adopts a promoted package for a context only if it beats its own local model on B's validation data by >= 0.02) minus `local-only`: contexts 0-2 >= +0.10 with the lower end > +0.05; contexts 3-5 lower end > -0.02. `blind` (accept-all promotion, B adopts the latest promoted package per context) minus `local-only` is reported, no threshold.
- **H6e (versioning, rollback, tamper evidence; property tests).** (i) promotions are chain entries with provenance and peer evidence; (ii) rollback to version n makes the active set and its hash identical to the set at version n, archived promotions stay in the log; (iii) editing or deleting a log entry is detected; (iv) every deterministic rejection reason fires on a crafted bad package (no consent, unknown or mismatching checkpoint, revoked origin, non-finite rule, wrong length, wrong norm, origin history rewritten).
- **H6f (cost reported).** Peer evaluations per package, messages per package, and the share of packages that needed peers are reported.

## What a pass would and would not mean
A pass shows that, in this simulation, peer evaluation on private data catches poisoned packages that valid metadata cannot, without blocking agreeing knowledge, and that versioned promotion can be rolled back. It does not show resistance to adaptive attackers (who could craft packages that look good on the peers' validation data), collusion among peers, privacy of the rule vectors, or anything about LLMs.

## Amendments

**A1 (14 Nov 2026, after run 1; thresholds NOT changed).** Registered verdicts: H6a PASS, H6b FAIL (honest shared-rule packages accepted by hybrid 0.722, needed 0.80), H6c PASS, H6d PASS, H6e PASS (properties), H6f reported. "0 of 180" poison accepted is bounded only to about 1.7% (rule of three); the bootstrap interval [0, 0] understates the uncertainty. See `M6-RESULTS.md`.
