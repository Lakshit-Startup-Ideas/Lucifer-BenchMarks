"""M8 integrated reproduction: rerun M2-M6 and M8 from scratch (one process each), compare every registered verdict flag and every number with the committed results,
and record wall-clock time and peak memory. Run: python -m lucv11.reproduce [out.json]. Exit code 1 if any verdict flag differs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS = [("m2", 20, "results/m2/run2.json"), ("m3", 30, "results/m3/run1.json"), ("m4", 30, "results/m4/run1.json"),
               ("m5", 30, "results/m5/run1.json"), ("m6", 30, "results/m6/run1.json"), ("m8", 30, "results/m8/run1.json")]
RUNNER = ("import json, resource, runpy, sys, time; mod = sys.argv[1]; sys.argv = [mod] + sys.argv[2:]; t = time.perf_counter(); runpy.run_module(mod, run_name='__main__'); "
          "rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss; "
          "print(json.dumps({'elapsed_s': time.perf_counter() - t, 'max_rss_mb': rss / 1e6 if sys.platform == 'darwin' else rss / 1e3}), file=sys.stderr)")


def flags(analysis: dict) -> dict:
    return {k: v for k, v in analysis.items() if k.endswith("_pass")}


def max_numeric_diff(a, b) -> float:
    """Largest absolute difference between two nested structures of numbers (a structural mismatch counts as infinite)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return 0.0 if a == b else float("inf")
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b)
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return float("inf")
        return max((max_numeric_diff(a[k], b[k]) for k in a), default=0.0)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return float("inf")
        return max((max_numeric_diff(x, y) for x, y in zip(a, b)), default=0.0)
    return 0.0 if a == b else float("inf")


def compare(committed: dict, fresh: dict) -> dict:
    old_flags, new_flags = flags(committed), flags(fresh)
    return {"flags_equal": old_flags == new_flags and bool(old_flags), "flags": new_flags,
            "differing_flags": {k: (old_flags.get(k), new_flags.get(k)) for k in set(old_flags) | set(new_flags) if old_flags.get(k) != new_flags.get(k)},
            "max_numeric_diff": max_numeric_diff(committed, fresh)}


def run_all(out_path: str | None = None) -> dict:
    report: dict = {"experiments": {}, "all_flags_equal": True}
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    for name, seeds, committed_path in EXPERIMENTS:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fresh.json"
            proc = subprocess.run([sys.executable, "-c", RUNNER, f"lucv11.{name}", str(seeds), str(out)], capture_output=True, text=True, env=env, cwd=ROOT)
            if proc.returncode != 0:
                report["experiments"][name] = {"error": proc.stderr[-400:]}
                report["all_flags_equal"] = False
                continue
            cost = json.loads(proc.stderr.strip().splitlines()[-1])
            result = compare(json.loads((ROOT / committed_path).read_text())["analysis"], json.loads(out.read_text())["analysis"])
        report["experiments"][name] = {"seeds": seeds, **cost, **result}
        report["all_flags_equal"] &= result["flags_equal"]
    report["total_elapsed_s"] = sum(e.get("elapsed_s", 0.0) for e in report["experiments"].values())
    if out_path:
        Path(out_path).write_text(json.dumps(report, indent=1, sort_keys=True))
    return report


if __name__ == "__main__":
    result = run_all(sys.argv[1] if len(sys.argv) > 1 else None)
    for name, e in result["experiments"].items():
        print(f"{name}: " + (f"ERROR {e['error']}" if "error" in e else f"flags_equal={e['flags_equal']} max_numeric_diff={e['max_numeric_diff']:.3g} {e['elapsed_s']:.1f}s {e['max_rss_mb']:.0f}MB"))
    print("ALL VERDICTS REPRODUCED" if result["all_flags_equal"] else "MISMATCH")
    sys.exit(0 if result["all_flags_equal"] else 1)
