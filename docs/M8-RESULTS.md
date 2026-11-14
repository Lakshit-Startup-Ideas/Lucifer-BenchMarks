# M8 results: maturation and unseen task families

Code commit `a979fd3`; run 1 (14 Nov 2026), 30 seeds, raw data `results/m8/run1.json`. Registered hypotheses: `M8-PREREGISTRATION.md`.
Synthetic world and a small learner we authored. It says nothing about LLMs.

## Registered verdicts
| Hypothesis | Verdict | Evidence (mean, 95% interval, 30 paired seeds) |
|---|---|---|
| H8 maturation helps | **FAIL** | forgetting `anchor` minus `mature` = **+0.0104** [+0.0076, +0.0136] (needed >= 0.01 with lower end > 0: met); final accuracy `mature` minus `anchor` = **-0.0265** [-0.0332, -0.0202] (needed >= -0.01: missed). Means: anchor accuracy 0.738 / forgetting 0.021; mature 0.712 / 0.011 |
| H9a experience helps on new same-family contexts | **PASS** | experienced minus fresh, mean online accuracy over the first 40 examples: **+0.0648** [+0.0477, +0.0823]; 0.690 vs 0.625 |
| H9b experience does not hurt on unseen families | **FAIL** | experienced minus fresh **-0.0219** [-0.0431, +0.0010] (needed lower end > -0.03); 0.598 vs 0.620 |
| H9 overall | **FAIL** | both parts were required |

## What this establishes
1. **Maturation is a trade-off, not a free gain.** A schedule that lowers plasticity and raises consolidation with age halved forgetting (0.021 to 0.011) and cost 0.027 final accuracy. The brief's second half (resource efficiency) was **not testable**: steps per run are identical by construction.
2. **Experience carries over within a family.** A model that has learned 12 contexts of one family learns new contexts of that family faster than an untrained model (+0.065).
3. **Carry-over to a different family is not shown to be safe.** The mean is slightly negative and the interval touches zero; the registered "no harm" bound was missed. This supports the M6 rule that shared knowledge must be tested on the receiver before adoption.

## Reconciling with M4
M4's H4a(ii) said the learner got no faster across contexts (few-shot on the first 10 examples, late minus early, anchor and earlier contexts' interference included). M8's H9a, with a different protocol (first 40 examples, against an untrained model on identical data, no anchor while measuring), finds a benefit. So "no cross-context speed-up" was **specific to the first-10 late-minus-early metric**; it should not be quoted as "experience never helps". The M4 verdict itself is unchanged.

## Not established
Generalisation to unseen families in any real sense (one kind of change, a different shared direction); whether the maturation schedule shape or its constants are good (fixed in advance, not tuned); any resource benefit of maturation; anything about language models.

## Decision: ADR `decisions/0007-no-default-maturation-family-scoped-transfer.md`
