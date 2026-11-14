# ADR 0002: Executive subsystem as separable components, each gated by its own evidence

- **Date:** 14 Nov 2026
- **Status:** accepted for M4+ experiments; the capability claim stays **unvalidated**
- **Problem:** the brief asks whether an executive (working memory, goals, monitoring, conflict resolution, regulation of learning) should be a neural network, specialised modules, a hybrid, or avoid a single central bottleneck.
- **Decision:** build the executive as a **hybrid**: deterministic control logic plus small learned estimators, as independent components (`goal slot + eviction policy`, `monitor`, `estimates`, `cost-aware choice`), each behind a flag so it can be ablated. No single central learned reasoning network.
- **Reason:** `docs/M3-RESULTS.md` shows the components are separable and each helps only where its failure mode exists. The deterministic parts stay inspectable and auditable, and the permission boundary lives there.
- **Rejected:**
  - One central learned executive network: not tested; adds a bottleneck and an opaque component with no evidence it is needed.
  - Always-on full executive: the failure-free check shows pure overhead (4.2 control steps and +0.21 module cost per episode with zero gain).
- **Evidence limits:** designed world, our parameters, no language model, two of the registered checks failed (H3b because the benign world was not failure-free; `-conflict` saving 0.405 < 0.5 registered).
- **Next dependency:** repeat the dissociation on tasks we did not author (tool-use or multi-step tasks from the V1 task bank, with a language model as the worker) before any claim about planning or reasoning.
- **Implementation status:** `src/lucv11/m3.py`, 16 tests. **Validation status:** simulation only.
