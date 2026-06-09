from shared_core.llm import estimate_llm_cost


class CostTracker:
    """Tracks estimated LLM costs during agent runs."""

    def __init__(self):
        self.total_cost = 0.0
        self.calls: list[dict] = []

    def record_call(self, model: str, input_tokens: int, output_tokens: int, latency_ms: float):
        cost = estimate_llm_cost(model, input_tokens, output_tokens)
        self.total_cost += cost
        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "latency_ms": latency_ms,
        })

    def summary(self) -> dict:
        return {
            "total_cost": round(self.total_cost, 6),
            "total_calls": len(self.calls),
            "calls": self.calls,
        }
