"""The three promotion gates from docs/EXPERIMENT-PLAN.md, computed from the rows of a run."""
from __future__ import annotations

from .stats import PRIMARY_PHASES, paired_bootstrap, task_means

RETENTION_MARGIN = 0.05
MASTERED = 0.8


def evaluate(rows: list[dict], audits: list[dict], resamples: int = 10_000) -> dict:
    base = task_means(rows, "baseline")
    lucifer = task_means(rows, "lucifer")
    irrelevant = task_means(rows, "irrelevant")

    d_ab = paired_bootstrap(base, lucifer, resamples)
    d_cb = paired_bootstrap(irrelevant, lucifer, resamples) if irrelevant else (0.0, 0.0, 0.0)
    if d_ab[1] > 0 and d_cb[1] > 0:
        verdict = "improves"
    elif d_ab[2] < 0:
        verdict = "hurts"
    else:
        verdict = "no effect detected"
    gate1 = {"passed": verdict == "improves", "verdict": verdict,
             "lucifer_minus_baseline": d_ab, "lucifer_minus_irrelevant": d_cb,
             "detail": "interval = 95% paired bootstrap over tasks; both intervals must sit above zero"}

    # Retention. The "mastered" tasks are chosen on half of the seeds and the drop is measured on the other half. Choosing and measuring on the
    # same runs would pick tasks the baseline happened to get lucky on, and regression to the mean would then look like forgetting.
    all_phases = ("similar", "transfer", "replay")
    seeds = sorted({r["seed"] for r in rows})
    select, measure = set(seeds[0::2]), set(seeds[1::2])
    base_sel = task_means(rows, "baseline", all_phases, seeds=select)
    mastered = [t for t, v in base_sel.items() if v >= MASTERED] if measure else []
    base_m, luc_m = task_means(rows, "baseline", all_phases, seeds=measure), task_means(rows, "lucifer", all_phases, seeds=measure)
    mastered = [t for t in mastered if t in base_m]
    drop = (sum(base_m[t] - luc_m.get(t, 0.0) for t in mastered) / len(mastered)) if mastered else 0.0
    # With no task the baseline masters (or too few seeds to split) there is nothing to lose: "inconclusive", not a pass.
    gate2 = {"passed": bool(mastered) and drop <= RETENTION_MARGIN, "inconclusive": not mastered, "mastered_tasks": len(mastered), "mean_drop": drop,
             "detail": f"tasks the baseline solves at least {MASTERED:.0%} of the time on half the seeds; lucifer may lose at most {RETENTION_MARGIN:.0%} of that on the other half"}

    audited = [a for a in audits if a["condition"] in ("lucifer", "irrelevant")]
    gate3 = {"passed": bool(audited) and all(a["ok"] for a in audited), "runs_audited": len(audited),
             "detail": "hash chain verifies, rollback reproduces the earlier version exactly, every lesson has provenance"}
    return {"gate1_improvement": gate1, "gate2_retention": gate2, "gate3_auditability": gate3,
            "all_passed": gate1["passed"] and gate2["passed"] and gate3["passed"]}
