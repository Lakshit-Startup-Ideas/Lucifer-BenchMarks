from __future__ import annotations

import json
from pathlib import Path

from .gates import evaluate
from .stats import paired_bootstrap, task_means


def load(folder: Path) -> tuple[list[dict], list[dict], dict]:
    return json.loads((folder / "rows.json").read_text()), json.loads((folder / "audits.json").read_text()), json.loads((folder / "meta.json").read_text())


def render(rows: list[dict], audits: list[dict], meta: dict) -> str:
    lines = [f"Run {meta['run_id']} · backend {meta['backend']} · seeds {len(meta['seeds'])} · lessons shown per task {meta['k']}", ""]
    lines.append(f"{'condition':<10} {'similar':>9} {'transfer':>9} {'replay':>8} {'pass@2 (sim+xfer)':>19} {'avg tokens/task':>16}")
    for cond in ("baseline", "lucifer", "irrelevant"):
        sel = [r for r in rows if r["condition"] == cond]
        if not sel:
            continue
        cell = lambda ph: f"{sum(task_means(rows, cond, (ph,)).values()) / max(1, len(task_means(rows, cond, (ph,)))):.0%}"
        p2 = task_means(rows, cond, ("similar", "transfer"), "pass_at_2")
        tokens = sum(r["prompt_tokens"] + r["completion_tokens"] for r in sel) / len(sel)
        lines.append(f"{cond:<10} {cell('similar'):>9} {cell('transfer'):>9} {cell('replay'):>8} {sum(p2.values()) / max(1, len(p2)):>19.0%} {tokens:>16.0f}")
    g = evaluate(rows, audits)
    g1, g2, g3 = g["gate1_improvement"], g["gate2_retention"], g["gate3_auditability"]
    iv = lambda t: f"{t[0]:+.2f} (95% interval {t[1]:+.2f} to {t[2]:+.2f})"
    lines += ["", "Gate 1 · improvement: " + ("PASS" if g1["passed"] else "FAIL") + f"  [{g1['verdict']}]",
              f"    lucifer − baseline: {iv(g1['lucifer_minus_baseline'])}", f"    lucifer − irrelevant: {iv(g1['lucifer_minus_irrelevant'])}",
              f"Gate 2 · retention:   {'INCONCLUSIVE (the baseline masters no task, so there is nothing to lose)' if g2['inconclusive'] else ('PASS' if g2['passed'] else 'FAIL')}  mean drop {g2['mean_drop']:+.2f} over {g2['mastered_tasks']} mastered tasks",
              f"Gate 3 · auditability: {'PASS' if g3['passed'] else 'FAIL'}  {g3['runs_audited']} memory stores audited",
              "", "All three gates: " + ("PASS" if g["all_passed"] else "NOT passed")]
    return "\n".join(lines)
