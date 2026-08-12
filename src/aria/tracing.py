"""ARIA execution tracing built on shared_core canonical spans.

``TraceLog`` records a step-by-step trace of an agent run and produces, in
addition to the human-readable entry list, a list of ``shared_core.tracing.Span``
objects (one root span per run plus one child span per tool call / decision).
The spans are AgentTrace-compatible (``trace_id``/``span_id``/``parent_span_id``/
``span_type``/``status``/timings/attributes) so the run can be ingested by an
observability backend or POSTed to a collector via ``shared_core.tracing.emit_span``.
"""

import time
from typing import Any, Dict, List, Optional

from shared_core.tracing import Span, SpanStatus, SpanType, new_trace_id


class TraceLog:
    """Records reasoning, decisions, and tool calls for one agent run."""

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or new_trace_id()
        self.entries: List[Dict[str, Any]] = []
        self.spans: List[Span] = []
        self.start_time = time.time()
        # Root span for the whole run; finalized in summary().
        self._root = Span(
            trace_id=self.trace_id,
            name="agent.run",
            span_type=SpanType.OTHER,
            start_ms=time.perf_counter() * 1000.0,
        )
        self.spans.append(self._root)

    @property
    def root_span_id(self) -> str:
        return self._root.span_id

    def add_reasoning(self, thought: str) -> None:
        self.entries.append(
            {"step": len(self.entries) + 1, "type": "reasoning", "content": thought}
        )

    def add_decision(self, name: str, detail: str, attributes: Optional[dict] = None):
        """Record a routing/approval decision as both an entry and a span."""
        self.entries.append(
            {
                "step": len(self.entries) + 1,
                "type": "decision",
                "name": name,
                "content": detail,
            }
        )
        now = time.perf_counter() * 1000.0
        self.spans.append(
            Span(
                trace_id=self.trace_id,
                parent_span_id=self._root.span_id,
                name=name,
                span_type=SpanType.DECISION,
                start_ms=now,
                end_ms=now,
                attributes=attributes or {"detail": detail},
            )
        )

    def add_tool_call(
        self,
        tool_name: str,
        params: dict,
        result: Any,
        latency_ms: float,
        *,
        status: str = "ok",
    ) -> None:
        """Record a tool call as a human-readable entry plus a child span."""
        self.entries.append(
            {
                "step": len(self.entries) + 1,
                "type": "tool_call",
                "tool": tool_name,
                "params": params,
                "result": str(result)[:500],
                "latency_ms": round(latency_ms, 2),
                "status": status,
            }
        )
        end = time.perf_counter() * 1000.0
        self.spans.append(
            Span(
                trace_id=self.trace_id,
                parent_span_id=self._root.span_id,
                name=f"tool.{tool_name}",
                span_type=SpanType.TOOL,
                status=SpanStatus.OK if status == "ok" else SpanStatus.ERROR,
                start_ms=end - latency_ms,
                end_ms=end,
                attributes={
                    "tool": tool_name,
                    "params": params,
                    "result": str(result)[:500],
                },
            )
        )

    def finalize(self) -> None:
        """Close the root span if not already closed."""
        if self._root.end_ms is None:
            self._root.end_ms = time.perf_counter() * 1000.0

    def span_dicts(self) -> List[Dict[str, Any]]:
        """Return all spans as plain dicts (AgentTrace-compatible)."""
        return [s.to_dict() for s in self.spans]

    def summary(self) -> dict:
        self.finalize()
        return {
            "trace_id": self.trace_id,
            "total_steps": len(self.entries),
            "duration_ms": round((time.time() - self.start_time) * 1000, 2),
            "entries": self.entries,
            "spans": self.span_dicts(),
        }
