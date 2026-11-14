# ADR 0007: No maturation schedule by default; treat experience as family-scoped and verify before cross-family use

- **Date:** 14 Nov 2026
- **Status:** accepted; both points stay open research
- **Problem:** the brief asks whether maturation improves stability and resource efficiency (H8) and whether the architecture generalises to unseen task families (H9).
- **Decision:**
  1. The default consolidation stays the constant anchor of ADR 0003. A maturation schedule (falling plasticity, rising anchor strength) is **not** adopted: it halved forgetting but lost 0.027 accuracy, outside the registered tolerance, and its efficiency claim was untestable.
  2. Learned experience is **family-scoped**: expect benefit on the same family (+0.065); do **not** assume benefit on a different family (-0.022, interval touching zero). Any cross-family reuse must pass the receiver-side test already required by ADR 0005.
- **Evidence:** `docs/M8-RESULTS.md`.
- **Rejected:** adopting maturation on the forgetting gain alone (ignores the accuracy cost); claiming general transfer from the same-family result.
- **Open:** schedule shape and constants (untuned); a resource-efficiency test where maturation changes compute (for example pruning or freezing with age); a real change of family (different input distribution), not only a different shared direction.
- **Implementation status:** `src/lucv11/m8.py`, 5 tests. **Validation status:** simulation only.
