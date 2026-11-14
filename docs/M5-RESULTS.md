# M5 results: parent coordinator, independent children, and when sharing helps

Code commit `f11766c`; experiment run 1 (14 Nov 2026), 30 seeds, raw data `results/m5/run1.json`. Registered hypotheses: `M5-PREREGISTRATION.md`. Threat model and its limits: `M5-THREAT-MODEL.md`.
An in-process prototype and a synthetic stream we authored. It says nothing about LLMs, about real users' knowledge, or about the security of a deployed system.

## Property hypotheses (tests in `tests/test_distributed.py`, 31 tests; all pass)
| Property | Verdict | What the test does |
|---|---|---|
| P1 registration | PASS | unknown and revoked ids rejected; rejection log holds the reason only, never the payload |
| P2 authentication | PASS | a child using another child's id fails the HMAC; a tampered payload fails the HMAC |
| P3 replay protection | PASS | a replayed or out-of-order sequence number is rejected |
| P4 schema allowlist | PASS | 9 schema-violating payloads, missing fields, unknown types, free-text names, NaN/infinity, oversize, 7 malformed envelopes and a non-serialisable payload are all rejected; the parent keeps serving afterwards |
| P5 no raw leakage | PASS | a canary experience (and its content hash and learned values) is absent from a full export of the parent's state |
| P6 independence | PASS | training child A leaves child B's parameter hash unchanged; stores and ledgers are separate objects; the parent holds no child references |
| P7 anchored audit | PASS | an honest child verifies, even after appending; a history rewritten with recomputed hashes, a truncated history, an anchor regression and an anchor fork are all caught |
| P8 checkpoint integrity | PASS | restore requires the parent's recorded hash; a tampered local checkpoint is refused |
| P9 audit trail | PASS | registration, heartbeat, checkpoint, evaluation, rejection and revocation each append to the parent's chain, which verifies and detects an edit |

**Do the tests bite?** Mutation check (each security check disabled in a copy, tests rerun from that copy): MAC check off -> 1 test fails; replay check off -> 1 fails; schema check off -> 11 fail; revocation ignored -> 1 fails; anchor ignored in `verify_child` -> 1 fails; payload leaked into the rejection log -> 1 fails. An earlier run of this check passed every mutant because pytest imported the unmutated code (path trap); it was redone with the tests copied beside each mutant and each mutation confirmed to take effect.

## Statistical hypotheses (30 paired seeds, 95% interval)
| Hypothesis | Verdict | Evidence |
|---|---|---|
| H5a sharing hurts when rules conflict | **PASS** | personal minus pooled = +0.147 [+0.132, +0.163] (needed >= +0.10, lower end > +0.05); personal 0.801 vs pooled 0.654 |
| H5b sharing helps when rules agree | **FAIL** | pooled minus personal = +0.0085 [+0.0006, +0.0162] (needed >= +0.02); personal 0.804 vs pooled 0.812 |

## What this establishes
1. The prototype **enforces its own rules in-process**: only a registered child with a valid, fresh, well-formed metadata message is accepted; raw data does not reach the parent through the protocol; histories are checked against anchors.
2. **The cost of sharing is asymmetric in this setting**: pooling two tenants when their rules conflict costs 0.147 accuracy, while pooling when they agree gains only 0.009. A review step (M6) therefore must test agreement and default to not sharing.
3. The pooled gain is small partly because one tenant's data already saturates this learner at about 0.80 (not tested why); with a learner that benefits more from data, the gain could be larger.

## What it does not establish
- Security of a deployed system (see the threat model's "NOT covered" list): no real key management, transport security, rate limiting or protection against covert channels or against inference from parameters, which M6 will have to face when knowledge is shared.
- That real tenants' knowledge agrees or conflicts in this way, or anything about LLMs.

## Decision: ADR `decisions/0004-parent-child-metadata-only-protocol.md`
