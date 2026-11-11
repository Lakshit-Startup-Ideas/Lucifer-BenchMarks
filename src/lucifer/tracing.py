"""OpenTelemetry-style traces for every task solve: one trace per solve, with nested spans for each processing step.

Times sit on a trace-local clock that starts at 0 and advances by each step's duration, so a trace reads as a waterfall even when a
backend only reports how long it took (simulated agents report a made-up latency and mark it `simulated`). Real backends report real
latency, and real steps (retrieval, test runs) are timed for real.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    kind: str  # root | retrieval | prompt | attempt | llm | execution | memory
    start_ms: float = 0.0
    duration_ms: float = 0.0
    status: str = "ok"  # ok | error
    attrs: dict = field(default_factory=dict)

    def set(self, **attrs) -> None:
        self.attrs.update(attrs)

    def to_dict(self) -> dict:
        return {"trace_id": self.trace_id, "span_id": self.span_id, "parent_id": self.parent_id, "name": self.name, "kind": self.kind,
                "start_ms": round(self.start_ms, 3), "duration_ms": round(self.duration_ms, 3), "status": self.status, "attrs": self.attrs}


class Tracer:
    def __init__(self, trace_id: str, root_name: str, **root_attrs) -> None:
        self.trace_id = trace_id
        self.spans: list[Span] = []
        self._clock = 0.0
        self._stack: list[Span] = []
        self._n = 0
        self.root = self._open(root_name, "root", root_attrs)

    def _open(self, name: str, kind: str, attrs: dict) -> Span:
        self._n += 1
        parent = self._stack[-1].span_id if self._stack else None
        span = Span(self.trace_id, f"{self.trace_id}/{self._n}", parent, name, kind, self._clock, 0.0, "ok", dict(attrs))
        self.spans.append(span)
        self._stack.append(span)
        return span

    @contextmanager
    def span(self, name: str, kind: str, **attrs):
        span = self._open(name, kind, attrs)
        began = time.perf_counter()
        try:
            yield span
        finally:
            self._stack.pop()
            elapsed = (time.perf_counter() - began) * 1000
            has_children = any(s.parent_id == span.span_id for s in self.spans)
            if has_children:
                span.duration_ms = self._clock - span.start_ms  # a parent lasts as long as its steps
            else:
                span.duration_ms = span.duration_ms or elapsed  # a step may set its own (reported) duration before it closes
                self._clock = span.start_ms + span.duration_ms

    def finish(self, status: str = "ok", **attrs) -> list[dict]:
        self._stack.pop()
        self.root.duration_ms = self._clock - self.root.start_ms
        self.root.status = status
        self.root.set(**attrs)
        return [s.to_dict() for s in self.spans]
