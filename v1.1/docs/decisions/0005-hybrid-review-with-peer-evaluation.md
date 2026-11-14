# ADR 0005: Knowledge promotion needs deterministic checks plus peer evaluation on private data; versioned and reversible

- **Date:** 14 Nov 2026
- **Status:** accepted for M7/M8 design; adaptive-attacker resistance and package privacy **unvalidated**
- **Problem:** the brief asks for a review mechanism that evaluates learned knowledge before it becomes shared, with explicit approval, rejection, rollback and versioning, and says information learned by one user must not automatically be shared with another.
- **Decision:**
  1. Nothing is shared by default; a package needs the origin's explicit consent flag.
  2. **Deterministic checks first** (consent, registered and active origin, provenance against the parent's recorded checkpoint and anchor, audited history, well-formed rule) as a gate, **never as sufficient evidence of benefit**.
  3. **Peer evaluation on private data**: independent children score the package against their own local model and report only two numbers; promote only if all peers improve by the margin (0.05; 0.10 when it conflicts with the active package).
  4. Promotions and rollbacks are entries on a Ledger v2 chain with ever-increasing version ids; rollback archives, never deletes; the active set is recomputed by replay.
  5. A receiving child adopts a promoted package only if it beats its own local model on its own validation data.
- **Evidence:** `docs/M6-RESULTS.md`: poison acceptance accept-all 100%, deterministic 100%, hybrid 0% of 180; honest-shared acceptance 72%; tenant B +0.109 on shared contexts, blind adoption -0.103 and -0.146; 23 tests, 8 mutants killed.
- **Rejected:**
  - Deterministic-only review: accepted every poisoned package.
  - Accept-all: measurably harmful (blind adoption).
  - A learned (neural) reviewer: not built, no non-circular training data yet; deferred.
- **Trade-offs:** 28% of useful packages were blocked, and every promotion costs peer messages and peer compute. The strictness (all peers, margin 0.05) is untuned.
- **Not validated:** an attacker who optimises against the peers' validation data; colluding peers; rule-vector privacy; scale (more than two peers, many contexts).
- **Implementation status:** `src/lucv11/knowledge.py`, `m6.py`, `distributed.py` (`export_package`, checkpoint anchors). **Validation status:** simulation only.
