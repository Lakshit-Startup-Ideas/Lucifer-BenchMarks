# ADR 0004: Parent/child protocol is metadata-only, authenticated, anchored; sharing defaults to off

- **Date:** 14 Nov 2026
- **Status:** accepted for M6; deployment security **not** validated
- **Problem:** the brief asks for a parent coordinator with independently developing children, isolation between users and organisations, controlled sharing, and no raw private conversations transmitted by default.
- **Decision:**
  1. Each child is its own trust boundary: own learner, own raw store, own ledger.
  2. The parent accepts only four-field-or-fewer **metadata messages** (heartbeat, checkpoint, evaluation) with an exact schema, strict value patterns, a size cap, HMAC authentication and strictly increasing sequence numbers; no free text.
  3. The parent keeps each child's last **ledger anchor** (head and length) and audits by prefix check; a child may append but not rewrite or truncate.
  4. Checkpoint restores are checked against the parent's recorded hash.
  5. **Sharing defaults to off.** Knowledge moves between children only through the M6 review mechanism, which must test whether the receiving tenant's rules agree.
- **Evidence:** `docs/M5-RESULTS.md`: 31 protocol tests, six mutants killed; personal vs pooled: -0.147 when rules conflict, +0.009 when they agree.
- **Rejected:**
  - A single shared model for all tenants: loses 0.147 when rules conflict, gains 0.009 when they agree.
  - Giving the parent read access to child data for convenience: breaks the isolation property and the privacy rule.
  - A separate foundation model per tenant: not tested here; the cost argument is in the assessment, and the smallest design that tests the hypothesis is one frozen base plus per-child adaptive components.
- **Known limits:** symmetric HMAC secrets handed over in-process; no transport security or key rotation; covert channels through allowed fields; inference from parameters is not addressed until M6.
- **Implementation status:** `src/lucv11/distributed.py`, `ledger.py` (`verify_prefix`), `m5.py`; 93 tests in total. **Validation status:** in-process simulation only.
