"""M8 overhead measurements (H10). Machine-specific wall-clock numbers: they show orders of magnitude on this Mac, not guarantees.
Measures: cost of a tool call through the engine vs calling the function directly, and cost of appending to and verifying a Ledger v2 chain."""
from __future__ import annotations

import json
import statistics
import sys
import time

from .ledger import Ledger
from .tools import Tool, ToolEngine

CALLS, LEDGER_ENTRIES, REPEATS = 3000, 10_000, 5


def _timed(fn) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def measure() -> dict:
    engine = ToolEngine(rate_limit=10**9)
    engine.register_tool(Tool("noop", "no-op", {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}, lambda a: "ok", "read"))
    engine.register_agent("a", {"read"})
    handler = engine.tools["noop"].handler
    direct = [_timed(lambda: [handler({"n": i}) for i in range(CALLS)]) / CALLS for _ in range(REPEATS)]
    through = [_timed(lambda: [engine.call("a", "noop", {"n": i}) for i in range(CALLS)]) / CALLS for _ in range(REPEATS)]

    def fill():
        ledger = Ledger()
        for i in range(LEDGER_ENTRIES):
            ledger.add(f"t{i}", "failure", f"lesson number {i} with some typical text", "run", i % 7)
        return ledger
    appended = [_timed(fill) / LEDGER_ENTRIES for _ in range(REPEATS)]
    ledger = fill()
    verified = [_timed(ledger.verify) / LEDGER_ENTRIES for _ in range(REPEATS)]
    us = lambda xs: round(statistics.median(xs) * 1e6, 2)
    return {"note": "median microseconds per operation on the machine that ran this; not a guarantee", "calls": CALLS, "ledger_entries": LEDGER_ENTRIES,
            "direct_handler_call_us": us(direct), "engine_call_us": us(through), "engine_overhead_us": round(us(through) - us(direct), 2),
            "ledger_append_us": us(appended), "ledger_verify_us_per_entry": us(verified)}


if __name__ == "__main__":
    result = measure()
    if len(sys.argv) > 1:
        json.dump(result, open(sys.argv[1], "w"), indent=1)
    print(json.dumps(result, indent=1))
