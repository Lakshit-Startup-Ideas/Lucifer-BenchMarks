"""Joins runs of the same experiment that covered different seeds (for example one CI job per seed) into one folder.

The runs must agree on everything except the seeds: same backend and model, same lessons-per-task, same retries, same number of tasks.
Seeds may not overlap, because the same seed twice would count one run double.
"""
from __future__ import annotations

import json
from pathlib import Path

SAME = ("backend", "k", "retries", "tasks")


def merge_runs(folders: list[Path], out: Path, run_id: str) -> dict:
    if not folders:
        raise ValueError("nothing to merge")
    metas = [json.loads((f / "meta.json").read_text()) for f in folders]
    for key in SAME:
        values = {json.dumps(m.get(key)) for m in metas}
        if len(values) > 1:
            raise ValueError(f"cannot merge runs that differ in {key}: {sorted(values)}")
    seeds = [s for m in metas for s in m["seeds"]]
    if len(seeds) != len(set(seeds)):
        raise ValueError(f"the runs share seeds: {sorted(s for s in set(seeds) if seeds.count(s) > 1)}")

    out.mkdir(parents=True, exist_ok=True)
    for name in ("rows.json", "audits.json", "memories.json"):
        merged: list = []
        for f in folders:
            merged += json.loads((f / name).read_text())
        (out / name).write_text(json.dumps(merged))
    for name in ("attempts.jsonl", "spans.jsonl"):
        lines: list[str] = []
        for f in folders:
            lines += [ln for ln in (f / name).read_text().splitlines() if ln.strip()]
        (out / name).write_text("\n".join(lines) + "\n")
    meta = {**metas[0], "seeds": sorted(seeds), "run_id": run_id, "merged_from": [m["run_id"] for m in metas]}
    (out / "meta.json").write_text(json.dumps(meta))
    return meta
