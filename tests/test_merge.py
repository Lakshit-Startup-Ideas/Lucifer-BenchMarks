import json

import pytest

from lucifer.backends.sim import SimBackend
from lucifer.cli import main
from lucifer.experiment import Config, run_experiment
from lucifer.merge import merge_runs
from lucifer.report import load
from lucifer.sandbox import FastExecutor
from lucifer.tasks import task_set


def _run(tmp_path, name, seeds):
    out = tmp_path / name
    run_experiment(Config(SimBackend("learner"), FastExecutor(), seeds=seeds, run_id=name, out_dir=out, tasks=task_set("convention")))
    return out


def test_merging_split_seeds_equals_running_them_together(tmp_path):
    a, b = _run(tmp_path, "a", (0,)), _run(tmp_path, "b", (1, 2))
    whole = _run(tmp_path, "whole", (0, 1, 2))
    merged = tmp_path / "merged"
    meta = merge_runs([a, b], merged, "merged")
    assert meta["seeds"] == [0, 1, 2] and meta["merged_from"] == ["a", "b"]
    rows_m, audits_m, _ = load(merged)
    rows_w, audits_w, _ = load(whole)
    key = lambda r: (r["seed"], r["condition"], r["phase"], r["task_id"])
    assert sorted((key(r), r["pass_at_1"]) for r in rows_m) == sorted((key(r), r["pass_at_1"]) for r in rows_w)
    assert len(audits_m) == len(audits_w)
    assert len((merged / "spans.jsonl").read_text().splitlines()) == len((whole / "spans.jsonl").read_text().splitlines())


def test_overlapping_seeds_are_refused(tmp_path):
    a, b = _run(tmp_path, "a", (0, 1)), _run(tmp_path, "b", (1, 2))
    with pytest.raises(ValueError, match="share seeds"):
        merge_runs([a, b], tmp_path / "m", "m")


def test_runs_of_different_experiments_are_refused(tmp_path):
    a = _run(tmp_path, "a", (0,))
    b = _run(tmp_path, "b", (1,))
    meta = json.loads((b / "meta.json").read_text())
    (b / "meta.json").write_text(json.dumps({**meta, "backend": "groq:other"}))
    with pytest.raises(ValueError, match="differ in backend"):
        merge_runs([a, b], tmp_path / "m", "m")


def test_merge_command(tmp_path, capsys):
    a, b = _run(tmp_path, "a", (0,)), _run(tmp_path, "b", (1,))
    assert main(["merge", str(a), str(b), "--out", str(tmp_path / "m"), "--run-id", "m"]) == 0
    assert "2 seeds" in capsys.readouterr().out
