# ADR 0003: Consolidation anchor as the default protection; event-sourced learning; replay local-only and optional

- **Date:** 14 Nov 2026
- **Status:** accepted for M5+ experiments; cross-context transfer and any LLM claim stay **unvalidated**
- **Problem:** the brief asks for retention without catastrophic forgetting, a learning lifecycle that separates logging from learning, and no transmission of raw private experience by default.
- **Decision:**
  1. Default continual-learning protection is a **parameter-space consolidation anchor** (L2 pull toward the previous snapshot), which stores no raw experience.
  2. **Replay is optional, local-only**, and only worth enabling with a buffer of roughly 30% of the stream or more; it is never shared.
  3. **Retrieval stays** as a complementary component (it cannot forget, and it carries the V1 evidence), but the hybrid of retrieval and parameters is untested.
  4. Learning is **event-sourced**: experience events, learning events and checkpoints are separate ledger-v2 records; raw content stays in a local store; unlearning = rebuild from a checkpoint without the record, never "delete the row".
- **Evidence:** `docs/M4-RESULTS.md` (anchor forgetting 0.159 to 0.021 at -0.014 accuracy; replay -0.023 at 100 slots, +0.043 at 300, +0.060 at 960; H4e property tests).
- **Rejected:**
  - Replay as the default: needs large raw storage, which conflicts with the privacy rule; and the registered 100-slot version made forgetting worse.
  - Retrieval only: no forgetting but lower final accuracy (0.711 vs 0.752) and all raw experience retained.
  - "Delete the event to unlearn": parameters keep the influence (tested).
- **Trade-offs:** the anchor slows adaptation (small accuracy cost) and its strength is untuned; it protects only what the snapshot covers.
- **Not shown:** that experience makes new learning faster (H4a failed); behaviour on language models.
- **Implementation status:** `src/lucv11/learner.py`, `events.py`, `m4.py`; 59 tests in total. **Validation status:** simulation only.
