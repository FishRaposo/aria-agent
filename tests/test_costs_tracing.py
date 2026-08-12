"""Cost tracking + trace emission tests (golden, deterministic)."""

from shared_core.pricing import calculate_cost
from shared_core.tracing import SpanType

from aria.costs import CostTracker
from aria.tracing import TraceLog


class TestCostTracker:
    def test_records_and_sums(self):
        tracker = CostTracker()
        tracker.record_call("gpt-4o-mini", 1000, 500, 42.0)
        summary = tracker.summary()
        assert summary["total_calls"] == 1
        assert summary["total_cost"] > 0.0

    def test_cost_matches_shared_pricing(self):
        # Golden: tracker must agree with shared_core.pricing exactly.
        tracker = CostTracker()
        cost = tracker.record_call("gpt-4o", 1_000_000, 1_000_000, 10.0)
        assert cost == calculate_cost("gpt-4o", 1_000_000, 1_000_000)
        # gpt-4o = $5/1M in, $15/1M out -> $20 for 1M+1M.
        assert abs(cost - 20.0) < 1e-9

    def test_estimate_passthrough(self):
        assert CostTracker.estimate("gpt-4o-mini", 1000, 0) == calculate_cost(
            "gpt-4o-mini", 1000, 0
        )

    def test_summary_has_percentiles(self):
        tracker = CostTracker()
        for lat in (10.0, 20.0, 30.0):
            tracker.record_call("gpt-4o-mini", 100, 50, lat)
        summary = tracker.summary()
        assert "p95_latency_ms" in summary
        assert summary["total_requests"] == 3


class TestTraceLog:
    def test_root_span_created(self):
        trace = TraceLog()
        assert trace.spans[0].name == "agent.run"
        assert trace.spans[0].span_id == trace.root_span_id

    def test_tool_call_emits_child_span(self):
        trace = TraceLog()
        trace.add_tool_call("calculator", {"expression": "1+1"}, "Result: 2", 5.0)
        tool_spans = [s for s in trace.spans if s.span_type == SpanType.TOOL]
        assert len(tool_spans) == 1
        assert tool_spans[0].name == "tool.calculator"
        assert tool_spans[0].parent_span_id == trace.root_span_id

    def test_decision_span(self):
        trace = TraceLog()
        trace.add_decision("route", "tool=calculator")
        decision_spans = [s for s in trace.spans if s.span_type == SpanType.DECISION]
        assert len(decision_spans) == 1

    def test_summary_shape(self):
        trace = TraceLog()
        trace.add_reasoning("thinking")
        trace.add_tool_call("calculator", {}, "ok", 1.0)
        summary = trace.summary()
        assert summary["trace_id"]
        assert summary["total_steps"] == 2
        assert "spans" in summary
        # All spans share the trace id (AgentTrace-compatible).
        assert all(s["trace_id"] == summary["trace_id"] for s in summary["spans"])

    def test_error_span_status(self):
        trace = TraceLog()
        trace.add_tool_call("x", {}, "boom", 1.0, status="error")
        err = [s for s in trace.spans if s.name == "tool.x"][0]
        assert err.status.value == "error"
