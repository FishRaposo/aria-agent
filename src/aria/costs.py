"""ARIA per-run LLM cost tracking via aria.internal.vendor_core.

Wraps ``aria.internal.vendor_core.llmmetrics.LLMMetrics`` (which defaults cost to
``aria.internal.vendor_core.pricing.calculate_cost``) so cost/token/latency aggregation matches
the rest of the portfolio exactly. Each routing/response LLM call the agent makes
is recorded here and surfaced in the run's cost summary.
"""

from typing import Any, Dict, Optional

from aria.internal.vendor_core.llmmetrics import LLMMetrics
from aria.internal.vendor_core.pricing import calculate_cost


class CostTracker:
    """Accumulates LLM-call telemetry for a single agent run."""

    def __init__(self) -> None:
        self._metrics = LLMMetrics()

    def record_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        *,
        error: Optional[str] = None,
    ) -> float:
        """Record one LLM call and return its USD cost."""
        call = self._metrics.record(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            latency_ms=latency_ms,
            error=error,
        )
        return call.cost_usd

    @staticmethod
    def estimate(model: str, input_tokens: int, output_tokens: int) -> float:
        """Convenience passthrough to the shared pricing table."""
        return calculate_cost(model, input_tokens, output_tokens)

    def summary(self) -> Dict[str, Any]:
        """Return the standard LLMMetrics summary for this run."""
        summary = self._metrics.summary()
        # Provide a couple of friendly aliases used by the API/dashboard.
        summary["total_cost"] = summary["estimated_cost"]
        summary["total_calls"] = summary["total_requests"]
        return summary
