import time
from typing import Any, Dict, List


class TraceLog:
    """Records a step-by-step trace of an agent run."""

    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def add_tool_call(self, tool_name: str, params: dict, result: Any, latency_ms: float):
        self.entries.append({
            "step": len(self.entries) + 1,
            "type": "tool_call",
            "tool": tool_name,
            "params": params,
            "result": str(result)[:500],
            "latency_ms": round(latency_ms, 2),
        })

    def add_reasoning(self, thought: str):
        self.entries.append({
            "step": len(self.entries) + 1,
            "type": "reasoning",
            "content": thought,
        })

    def summary(self) -> dict:
        return {
            "total_steps": len(self.entries),
            "duration_ms": round((time.time() - self.start_time) * 1000, 2),
            "entries": self.entries,
        }
