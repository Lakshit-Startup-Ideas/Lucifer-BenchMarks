# ADR 0001: Dynamic topology is not adopted by default

- **Date:** 14 Nov 2026
- **Status:** accepted (revisit only after a new pre-registered test)
- **Problem:** the V1.1 brief asks whether dynamic topology outperforms an equivalent fixed topology, and warns against structural complexity without demonstrated necessity.
- **Decision:** the default V1.1 core is a fixed-topology recurrent/state-space model with parameter-level plasticity. Growth and pruning stay as experimental modules.
- **Evidence:** `docs/M2-RESULTS.md` (run 2, 20 seeds). Triangular (safe) growth: exact retention but 0.417 vs 0.068 NMSE against a matched fixed network, and no compute saving. Rewiring growth: good capacity, catastrophic loss of earlier readouts. Importance pruning: not better than random.
- **Alternatives considered:**
  - Adopt triangular growth for its exact retention: rejected, loses most of the capacity of an equal-size network.
  - Adopt rewiring growth with readout refit/replay: not tested yet, so not adopted. It is the first thing to test next (needs stored states or replay data, which interacts with the privacy rules for experience records).
- **Trade-offs:** we give up a possible efficiency gain that was not demonstrated; we keep simpler, auditable behaviour.
- **Implementation status:** `src/lucv11/dynnet.py`, `src/lucv11/m2.py`, 14 tests.
- **Validation status:** simulation only, one task family, one network type. Not validated on any language model.
