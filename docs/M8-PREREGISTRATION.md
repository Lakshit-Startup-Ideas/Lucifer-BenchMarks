# M8 pre-registration: closing the hypothesis list (maturation, unseen families) and integrated reproduction

Written BEFORE any M8 code or run (14 Nov 2026). Amendments go at the bottom.

## Why these two experiments
The V1.1 brief's minimum hypothesis list has ten items. M2-M7 covered adaptation (1), topology (2), executive (3), personalisation (4), transfer between children (5), retention (6), review (7). **Maturation (8) and generalisation to unseen task families (9)** were never tested, and **overhead (10)** was only measured piecemeal. M8 tests 8 and 9 on the M4 learner, and collects 10 from measurements already taken. It says nothing about LLMs; the world is synthetic and authored by us.

## Shared setup (as M4)
`x ~ N(0, I_20)`, binary label from a hidden linear rule per context, rules `w = 0.5 g + 0.5 s` (shared direction `g`, sparse part `s`, 3 active coordinates). Learner: shared matrix `U` (20x4) plus a head per context, logistic loss, SGD (`ParamModel`). 12 contexts in sequence, 80 examples each, online (predict, then one step), then 5 extra epochs over the phase. 30 seeds, paired, 95% bootstrap intervals (10,000 resamples). The consolidation anchor is the ADR 0003 default.

## H8: does maturation help? (brief item 8)
Maturation here = **plasticity falls and consolidation rises with developmental age** `t = 0..11` (phase index):
- `anchor` (control, ADR 0003): lr 0.1, anchor strength 1.0, constant.
- `mature`: `lr_t = 0.2 * 0.25^(t/11)` (0.2 down to 0.05) and anchor strength `lambda_t = 0.5 + 1.5 * t/11` (0.5 up to 2.0).
Metrics: final accuracy over all 12 contexts; forgetting (as M4). Steps per run are identical by construction, so the **resource-efficiency half of the brief's hypothesis is not testable here** and is declared untested.
- **H8 passes** if `mature` lowers forgetting by >= 0.01 (lower end of the interval > 0) AND final accuracy is no worse than `anchor` minus 0.01. FAILS otherwise.

## H9: does experience help on unseen task families? (brief item 9)
After 12 training contexts (family F1, direction `g1`), the model meets 4 new **same-family** contexts (`g1`, new sparse parts) and 4 **unseen-family** contexts (independent `g2`, different sparse parts). On each, 80 examples arrive online with one SGD step per example and nothing else. Compare the **experienced** model (shared `U` kept, fresh head per new context) with a **fresh** model (new `U`, trained the same way on the same data). Metric: mean online accuracy over the first 40 examples.
- **H9a (same family):** experienced minus fresh >= +0.05 with the lower end > +0.02.
- **H9b (unseen family: no harm):** experienced minus fresh with the lower end > -0.03.
FAILS if either part fails. Expectation recorded in advance: M4 found no cross-context speed-up (H4a ii), so H9a is likely to fail.

## H10: overhead (brief item 10) - no new experiment
A table of **measured** costs collected from M2-M7 results and a timed reproduction run: storage (raw experiences kept), extra control steps per episode, messages per package, wall-clock per experiment, test counts. The verdict on "does the architecture justify its overhead" is written in the technical report from that table and is not a registered statistic.

## Integrated reproduction (property, not statistic)
`scripts/reproduce.py` reruns M2-M6 and M8 with the committed seeds and compares every registered verdict flag with the committed result files. **Pass** = all flags equal, no exception. It records wall-clock time per experiment. It does not rerun the interop tests (needs the isolated venv) and cannot check anything that is not a flag.

## Amendments

**A1 (14 Nov 2026, after run 1; thresholds NOT changed).** H8 FAIL (forgetting -0.0104 as hoped, final accuracy -0.0265, tolerance was -0.01), H9a PASS (+0.0648), H9b FAIL (-0.0219, interval lower end -0.0431 vs bound -0.03), H9 overall FAIL. The `anchor` control reproduces M4's `P+anchor` exactly (test). See `M8-RESULTS.md`; note the reconciliation with M4's H4a(ii).
