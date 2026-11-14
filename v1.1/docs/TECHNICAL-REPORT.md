# Lucifer V1.1: technical report (14 Nov 2026)

Code: `~/Personal/lucifer-v11` (local git repo, not pushed), 2,293 source lines, 202 tests. V1 baseline: Lucifer-BenchMarks `fe08665` (untouched). Every claim below links to a results file; every experiment was pre-registered before it ran.

## 1. Bottom line
- **Built and tested:** a fixed-topology adaptive learner with consolidation, an event-sourced learning pipeline (logging is separate from learning; unlearning needs retraining), a parent/child protocol that moves metadata only, a review mechanism for sharing knowledge, a policy-enforcing tool engine with a handshake-era MCP adapter, an A2A lifecycle model, a runtime with crash recovery, a browser policy layer, and a reproduction harness.
- **Supported, in simulation only:** consolidation prevents most forgetting without storing raw experience; sharing between tenants helps only when their rules agree and hurts a lot when they conflict; review on private peer data blocks non-adaptive poison while letting most agreeing knowledge through; experience helps on new contexts of the **same** family.
- **Not supported:** dynamic topology (growth and pruning) beat nothing; maturation schedules traded accuracy for stability; experience on an **unseen** family was not shown safe; the executive's benefit exists only in worlds built to need it.
- **Not validated anywhere:** anything on a language model. All learning results are on small synthetic learners we authored. V1 (retrieval into a frozen LLM prompt) remains the only real-model evidence, and V1.1 did not rerun it.
- **Registered scorecard:** 21 threshold hypotheses: **10 passed, 11 failed** (failures are reported, thresholds were never moved). All property checks passed (event pipeline, parent/child protocol, review properties, tool engine, MCP, runtime, A2A model, browser policy).

## 2. The brief's ten hypotheses
| # | Question | Where | Result | Level of evidence |
|---|---|---|---|---|
| 1 | Does experience-driven adaptation improve future performance? | M4, M8 | Parameter adaptation beat 5-NN retrieval on final accuracy (0.752 vs 0.711, descriptive, +0.041 [0.032, 0.049]); same-family new contexts learned faster than from scratch (+0.065 [0.048, 0.082]); the registered first-10-examples speed-up test **failed** | simulation |
| 2 | Does dynamic topology beat an equal fixed topology? | M2 | **No.** Safe growth: exact retention but NMSE 0.417 vs 0.068; rewiring growth: capable but wipes old readouts; no compute saving; importance pruning = random | simulation |
| 3 | Does an executive improve planning and completion? | M3 | Components are separable and each helps only where its failure mode exists; +0.79 completion in the combined world; overhead 4-6 control steps per episode; two of three registered hypotheses failed | designed simulation (effect sizes follow our parameters) |
| 4 | Does personalised adaptation beat shared-only? | M5 | Yes when rules conflict (+0.147 [0.132, 0.163]); pooling gains only +0.0085 when rules agree (registered 0.02: failed) | simulation |
| 5 | Can useful knowledge transfer between independent systems? | M6 | Yes with review: poor tenant +0.109 [0.092, 0.125] on shared contexts, 0.000 harm on tenant-specific ones | simulation |
| 6 | Retention without catastrophic forgetting? | M4 | Anchor: forgetting 0.159 to 0.021 at -0.014 accuracy, no raw experience stored | simulation |
| 7 | Can review prevent harmful propagation? | M6 | 0 of 180 poisoned packages accepted (bound about 1.7%); metadata-only review accepted all of them; 28% of useful packages also blocked; adaptive attackers and collusion **untested** | simulation |
| 8 | Does maturation improve stability and efficiency? | M8 | Stability yes (forgetting 0.021 to 0.011), accuracy -0.027 (outside tolerance), efficiency **not testable** in this design: **failed as registered** | simulation |
| 9 | Does it generalise to unseen task families? | M8 | Same family +0.065; unseen family -0.022 [-0.043, +0.001]: **not shown safe, failed as registered** | simulation |
| 10 | Does the architecture justify its overhead? | M3-M8 | See section 4. No overall claim: the benefits are only shown in simulation | measured costs |

## 3. Claims ledger (what may be said, and with what wording)
| Claim | May say | May not say |
|---|---|---|
| Consolidation anchor | "reduced forgetting from 0.159 to 0.021 in a small simulated learner" | "solves catastrophic forgetting" |
| Dynamic topology | "did not help in our test; not adopted" | "dynamic networks do not work" |
| Executive | "four separable mechanisms, each useful only where needed, with measured overhead" | "improves reasoning or planning" |
| Review | "blocked all non-adaptive poisoned packages in 180 trials" | "prevents knowledge poisoning" |
| Parent/child | "metadata-only protocol with authentication, replay protection, anchored audit, tested in-process" | "secure" or "private by design" in deployment |
| MCP | "handshake-era MCP tools server, interoperates with the official Python SDK 2.3.0 client in auto and legacy modes" | "MCP compatible" without the era; support for 2026-07-28 |
| A2A | "in-process model of the v0.3.0 lifecycle and discovery" | "A2A compatible" |
| Browser | "policy layer over a fake driver" | "browser automation" or "safe against prompt injection" |
| Event sourcing | "replay reproduces training exactly; deleting a record does not unlearn, rebuilding from a checkpoint does" | "supports GDPR erasure" |
| Everything | "pre-registered, reproduced bit-exactly from scratch on this machine" | "AGI", "consciousness", "brain-like" |

## 4. Overhead (H10): measured costs
| Component | Cost | Source |
|---|---|---|
| Executive (monitor + goal slot) | 4.2 to 6.0 control steps per episode; with nothing able to fail: +4.2 steps and +0.21 module cost per episode for zero gain | M3 |
| Consolidation anchor | no stored experience; final accuracy -0.014 versus unprotected | M4 |
| Replay (the alternative) | needs 300 to 960 raw experiences kept (31 to 100% of the stream) for 0.043 to 0.060 less forgetting; conflicts with the local-only rule | M4 |
| Review | 4 evaluation messages per package; 28% of useful packages blocked | M6 |
| Tool engine | about 176 microseconds added per call (validation, permission check, thread hop, audit entry) | `results/m8/overhead.json` |
| Hash-chained audit | 2.65 microseconds per append; 1.6 microseconds per entry to verify (16 ms for 10,000 entries) | same |
| Whole reproduction | 67 s wall clock, peak 48 MB per experiment process, on one Mac | `results/m8/reproduction.json` |
**Reading:** the infrastructure overheads (engine, audit, protocol) are negligible next to any model or network call. The costs that matter are behavioural: the executive's control steps when nothing is wrong, the review's 28% false rejection, and replay's raw-data retention. Whether any of this pays off on a real model is **unknown**.

## 5. Reproducibility
- Pinned: numpy 2.3.3, pytest; Python 3.15.2 (the only version run locally; CI for 3.11 and 3.13 is written but has **never run on GitHub**).
- `python -m lucv11.reproduce` reran M2-M6 and M8 from scratch in separate processes: **all 23 verdict flags identical (the 21 hypotheses plus the M4 precondition and the composite H9), maximum numeric difference 0** (`results/m8/reproduction.json`). Not tested: another OS or CPU.
- Pre-registrations were committed before code and results; amendments are logged with reasons (M2 A1 changed task difficulty after an uninformative run; M3 A1 changed plan length before any run).
- Mutation checks of security tests: M5 6 of 6, M6 8 of 8, M7 21 of 22 (1 equivalent) killed; an earlier mutation run was invalid and redone.
- Existence proof: the V1 manifest is OpenTimestamps-stamped (pending Bitcoin confirmation at the time of writing); see `~/Personal/lucifer-private/PROOF-OF-EXISTENCE.md`. A timestamp shows a file existed by a date, not who wrote it, and it is not a patent.

## 6. Risks and known weaknesses
1. **No language-model validation.** The largest gap. Everything in V1.1 that is about learning is a toy.
2. **Authored worlds.** Effect sizes follow from our parameters; several results are mechanism checks.
3. **Adaptive attackers, collusion, rule-vector privacy** (membership inference) are untested; M6 shares rule vectors.
4. **Symmetric HMAC secrets handed over in-process**, no transport security, no key rotation; covert channels through allowed fields.
5. **Handler code is not isolated**: a timed-out tool keeps running; no sandbox.
6. **Original documents missing.** `ARCHITECTURE.md` and `USP_UNIQUE_FEATURES.pdf` were never found on this machine, so the traceability map to the original ideas is **not done** and nothing here is derived from them.
7. **V1 sandbox escape resistance** was never reviewed.

## 7. What to do next (highest value first)
1. Put the original documents in `~/Personal/lucifer-private/originals/`, then complete the idea-preservation matrix and record every departure.
2. Rerun the V1 task bank with a language model in the loop for the two questions that matter: does parameter-level adaptation (a small adapter or lesson-conditioned fine-tune, on a hosted or runner GPU, not the Mac) beat V1's retrieval on unseen tasks, and does the anchor protect earlier tasks?
3. Test an **adaptive** attacker against the review (packages optimised on the peers' validation data) and add clipping or noise to shared rule vectors.
4. Run the CI workflow on GitHub (it has never run) and decide whether V1.1 becomes a private GitHub repository.
5. A 2026-07-28 MCP variant and a real browser driver behind the policy layer, each as its own pre-registered step.

## 8. Index
Pre-registrations and results: `M2` to `M8` in this folder. Decisions: `decisions/0001` to `0007`. V1 findings: `V1-HASH-FINDINGS.md`. Threat model: `M5-THREAT-MODEL.md`. V1 assessment: `~/Personal/lucifer-private/V1.1-ASSESSMENT.md`.
