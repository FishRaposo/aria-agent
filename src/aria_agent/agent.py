"""AriaAgent — the central orchestrator (v0.3).

This is the canonical entry point for Aria. v0.3 unifies v0.1's tool agent
and v0.2's cross-provider model router into a single orchestrator.

**Two execution paths, one API surface:**

1. **Tool path (v0.1 preserved):** If a `ToolRegistry` is wired in and the
   query matches a tool keyword (calculate/search/read/task/email), the agent
   delegates to `KeywordRouterAgent` (the v0.1 reason-and-act loop, preserved
   verbatim). The result is wrapped in a `CooperationResult` so the API
   surface stays uniform.

2. **Model path (v0.2):** For everything else, the agent uses the
   cross-provider `ModelSelector` to pick the best (provider, model) pair,
   then runs the chosen `CooperationPattern` (cascade, plan_execute_validate,
   or ensemble). The pattern handles routing, escalation, and orchestration.

**Per-request state.** No module-level mutable state. The provider registry
and router are constructed once at app startup and shared across requests;
the tool registry and approval gate are wired at construction time; everything
else (memory, trace, cost tracking) is per-request.

**Why both paths matter:**

- Tools (calculator, web_search, file_reader, task_creator, email_draft) are
  fast, deterministic, and free. For "calculate 2 + 2", routing through a
  3,000-token LLM call wastes tokens and seconds. The tool path handles these
  queries in <1ms.
- Models are needed for open-ended reasoning, generation, and any query that
  doesn't match a tool. The model path picks the right one.

**Usage:**

```python
from aria_agent.tools import ToolRegistry
from aria_agent.builtin_tools import calculator, web_search, file_reader, task_creator, email_draft
from aria_agent.approvals import ApprovalGate
from aria_agent.providers import get_default_registry
from aria_agent.router import ModelSelector, get_default_routing_table

tools = ToolRegistry()
tools.register("calculator", CalculatorInput)(calculator)
# ... register others ...

agent = AriaAgent(
    registry=get_default_registry(),
    router=ModelSelector(get_default_routing_table()),
    tool_registry=tools,
    approval_gate=ApprovalGate(enabled=True),
)

# Tool path
result = await agent.run("calculate 2 + 2")
assert result.metadata["intent"] == "tool_call"

# Model path
result = await agent.run("Write a Python function to add two numbers")
assert result.metadata["intent"] == "model_call"
```

**Force mode:** Pass `force_mode="tool"` or `force_mode="model"` to skip
intent classification. Useful for testing or when the caller already knows
which path should run.
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .agents import KeywordRouterAgent
from .approvals import ApprovalGate
from .cooperation import (
    CascadePattern,
    CooperationPattern,
    CooperationResult,
    EnsemblePattern,
    PlanExecuteValidatePattern,
    StepResult,
)
from .costs import CostTracker
from .memory import AgentMemory
from .providers.registry import ProviderRegistry
from .router.selector import ModelSelector
from .tools import ToolRegistry
from .tracing import TraceLog


# Map of pattern name → pattern class for user-facing selection
_PATTERN_REGISTRY: dict[str, type[CooperationPattern]] = {
    "cascade": CascadePattern,
    "plan_execute_validate": PlanExecuteValidatePattern,
    "ensemble": EnsemblePattern,
}


# Tool keywords. Mirrors the v0.1 KeywordRouterAgent's `_plan_action` logic.
# The orchestrator uses this to decide whether to dispatch to a tool or
# route through a model. Keep in sync with KeywordRouterAgent._plan_action.
_TOOL_KEYWORDS: dict[str, list[str]] = {
    "calculator": ["calculate", "compute", "math"],
    "web_search": ["search", "find", "look up", "google"],
    "file_reader": ["read", "file", "open"],
    "task_creator": ["task", "remind", "todo", "create"],
    "email_draft": ["email", "draft"],
}


class Intent(str, Enum):
    """Whether the query should be handled by a tool or a model."""

    TOOL_CALL = "tool_call"
    MODEL_CALL = "model_call"


@dataclass
class IntentClassification:
    """Result of intent classification — which path will handle the query."""

    intent: Intent
    matched_tool: Optional[str] = None
    matched_keyword: Optional[str] = None
    reason: str = ""


class AriaAgent:
    """The central orchestrator. v0.3 = v0.1 (tools) + v0.2 (router/cooperation).

    Holds:
    - ProviderRegistry (v0.2) — the resolver for (provider, model) → live client
    - ModelSelector (v0.2) — the task → (primary, fallback, escalation) mapper
    - Optional ToolRegistry (v0.1) — when set, tool-path delegation is enabled
    - Optional ApprovalGate (v0.1) — auto-built when tool_registry is provided
    - Optional KeywordRouterAgent (v0.1) — auto-built when tool_registry is set
    - Pattern cache (v0.2) — instantiated CooperationPatterns, one per name
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        router: ModelSelector,
        *,
        tool_registry: Optional[ToolRegistry] = None,
        approval_gate: Optional[ApprovalGate] = None,
        max_steps: int = 5,
        default_pattern: str = "cascade",
    ):
        self.registry = registry
        self.router = router
        self.default_pattern = default_pattern
        self._patterns: dict[str, CooperationPattern] = {}

        # v0.1 components (optional). If tool_registry is provided, the tool
        # path is enabled. Otherwise, every query goes through the model path.
        self.tool_registry = tool_registry
        self.max_steps = max_steps

        # The v0.1 KeywordRouterAgent is the actual executor for tool calls.
        # We only build it if a tool_registry was provided — otherwise every
        # query goes through the model path and the legacy agent is unused.
        self.legacy_agent: Optional[KeywordRouterAgent] = None
        self.approval_gate: Optional[ApprovalGate] = approval_gate
        if tool_registry is not None:
            # Use the provided gate, or auto-build one with sensible defaults.
            gate = approval_gate if approval_gate is not None else ApprovalGate(enabled=True)
            self.approval_gate = gate
            self.legacy_agent = KeywordRouterAgent(
                tool_registry, gate, max_steps=max_steps
            )

    # ----- Intent classification ---------------------------------------------

    def classify_intent(self, task: str) -> IntentClassification:
        """Decide whether `task` should be handled by a tool or a model.

        Uses the registered tool names + keyword matching. If a tool name
        keyword appears in the task, the tool path is chosen. Otherwise, the
        model path.

        Returns an IntentClassification with the matched tool (if any) and
        a human-readable reason. The reason is included in the response
        metadata so callers can see which path was chosen and why.
        """
        # No tool registry → always use the model path
        if self.tool_registry is None or not self.tool_registry.tools:
            return IntentClassification(
                intent=Intent.MODEL_CALL,
                reason="No tools registered; using model path.",
            )

        lowered = task.lower()
        # Find the first tool whose keyword appears in the query
        for tool_name, keywords in _TOOL_KEYWORDS.items():
            if tool_name not in self.tool_registry.tools:
                continue  # Tool not actually registered; skip
            for keyword in keywords:
                if keyword in lowered:
                    # Special case: "calculate" without a numeric expression
                    # should still go to the model (no math to compute).
                    # This improves on KeywordRouterAgent's v0.1 behavior of
                    # returning ("calculator", {"expression": "0"}) when no
                    # expression is found — which is silly.
                    if tool_name == "calculator" and not re.search(r"\d", task):
                        return IntentClassification(
                            intent=Intent.MODEL_CALL,
                            matched_tool=tool_name,
                            matched_keyword=keyword,
                            reason=f"'{keyword}' matched but no numeric "
                            "expression; using model path for explanation.",
                        )
                    return IntentClassification(
                        intent=Intent.TOOL_CALL,
                        matched_tool=tool_name,
                        matched_keyword=keyword,
                        reason=f"Matched tool keyword '{keyword}' → {tool_name}",
                    )

        return IntentClassification(
            intent=Intent.MODEL_CALL,
            reason="No tool keyword matched; using model path.",
        )

    # ----- Pattern management -----------------------------------------------

    def get_pattern(self, name: Optional[str] = None) -> CooperationPattern:
        """Get a cooperation pattern by name, instantiating if needed.

        Patterns are cached on the agent so we don't reconstruct them on
        every request.
        """
        name = name or self.default_pattern
        if name not in self._patterns:
            if name not in _PATTERN_REGISTRY:
                raise ValueError(
                    f"Unknown cooperation pattern '{name}'. "
                    f"Available: {sorted(_PATTERN_REGISTRY.keys())}"
                )
            self._patterns[name] = _PATTERN_REGISTRY[name]()
        return self._patterns[name]

    def list_patterns(self) -> list[str]:
        """Return the names of available cooperation patterns."""
        return sorted(_PATTERN_REGISTRY.keys())

    # ----- Routing preview ---------------------------------------------------

    def preview_route(self, task: str) -> dict:
        """What would the router pick for this task?

        Useful for /agent/route/{task} endpoint and for debugging.
        Returns the routing decision as a plain dict (no model objects).
        """
        decision = self.router.select_for_task_description(task)
        return {
            "task_type": decision.task_type.value,
            "primary": _model_to_dict(decision.primary),
            "fallback": _model_to_dict(decision.fallback) if decision.fallback else None,
            "escalation": _model_to_dict(decision.escalation) if decision.escalation else None,
            "reason": decision.reason,
        }

    # ----- Main entry point --------------------------------------------------

    async def run(
        self,
        task: str,
        *,
        pattern: Optional[str] = None,
        budget: Optional[str] = None,
        force_mode: Optional[str] = None,
    ) -> CooperationResult:
        """Run a task — tool path or model path, decided automatically.

        Args:
            task: The user's request (free-form text)
            pattern: Which cooperation pattern to use (model path only):
                     "cascade", "plan_execute_validate", "ensemble".
                     Default = cascade.
            budget: "cheap" | "balanced" | "quality". Default = balanced.
                     Model path only.
            force_mode: "tool" or "model" — skip intent classification.
                        Useful for testing or when the caller knows which
                        path should run.

        Returns:
            CooperationResult with the final output and full step transcript.
            Tool-path results have metadata["intent"] == "tool_call" and
            pattern == "keyword_router". Model-path results have
            metadata["intent"] == "model_call".
        """
        # Decide the intent (unless forced)
        if force_mode == "tool":
            classification = IntentClassification(
                intent=Intent.TOOL_CALL,
                reason="Forced tool mode (force_mode='tool')",
            )
        elif force_mode == "model":
            classification = IntentClassification(
                intent=Intent.MODEL_CALL,
                reason="Forced model mode (force_mode='model')",
            )
        else:
            classification = self.classify_intent(task)

        # Tool path
        if classification.intent == Intent.TOOL_CALL:
            return await self._run_tool_path(task, classification)

        # Model path (default)
        return await self._run_model_path(
            task, pattern=pattern, budget=budget,
            classification=classification,
        )

    # ----- Tool path --------------------------------------------------------

    async def _run_tool_path(
        self,
        task: str,
        classification: IntentClassification,
    ) -> CooperationResult:
        """Run the task through the v0.1 KeywordRouterAgent.

        The legacy agent returns a plain string. We wrap it in a
        CooperationResult so the API surface stays uniform with the model
        path. Trace + cost info from the v0.1 run is preserved in metadata.
        """
        if self.legacy_agent is None:
            # Caller forced tool mode but no tool registry is wired in.
            # Fall back to model path with a clear metadata note.
            return await self._run_model_path(
                task,
                classification=IntentClassification(
                    intent=Intent.MODEL_CALL,
                    reason="Tool path requested but no tool registry wired; "
                    "falling back to model path.",
                ),
            )

        # Per-request state (v0.1 components)
        trace = TraceLog()
        cost_tracker = CostTracker()
        # Use a fresh memory for this request so concurrent requests don't
        # share conversation history.
        original_memory = self.legacy_agent.memory
        self.legacy_agent.memory = AgentMemory()
        try:
            output_str = self.legacy_agent.run(
                task, trace=trace, cost_tracker=cost_tracker,
            )
        finally:
            # Restore the original memory (defensive; the agent isn't supposed
            # to mutate it across requests).
            self.legacy_agent.memory = original_memory

        # Build a StepResult capturing the v0.1 tool call. Use the trace's
        # first tool_call entry if present, else synthesize one.
        tool_call = next(
            (e for e in trace.entries if e["type"] == "tool_call"),
            None,
        )
        if tool_call:
            step = StepResult(
                step_name="keyword_router_tool_call",
                provider_name="keyword_router",
                model_id="keyword_router",
                input_messages=[{"role": "user", "content": task}],
                output_text=output_str,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=tool_call.get("latency_ms", 0.0),
                cost_usd=0.0,  # v0.1 cost_tracker is a no-op stub
                success=True,
            )
        else:
            # No tool matched (legacy agent returned the LLM fallback or the
            # "no tool matched" string). Still record the run.
            step = StepResult(
                step_name="keyword_router_no_match",
                provider_name="keyword_router",
                model_id="keyword_router",
                input_messages=[{"role": "user", "content": task}],
                output_text=output_str,
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=trace.summary()["duration_ms"],
                cost_usd=0.0,
                success=True,
            )

        return CooperationResult(
            final_output=output_str,
            pattern="keyword_router",
            steps=[step],
            total_cost_usd=0.0,
            total_latency_ms=trace.summary()["duration_ms"],
            metadata={
                "intent": "tool_call",
                "matched_tool": classification.matched_tool,
                "matched_keyword": classification.matched_keyword,
                "classification_reason": classification.reason,
                "v0_1_trace": trace.summary(),
                "v0_1_cost": cost_tracker.summary(),
            },
        )

    # ----- Model path -------------------------------------------------------

    async def _run_model_path(
        self,
        task: str,
        *,
        pattern: Optional[str] = None,
        budget: Optional[str] = None,
        classification: Optional[IntentClassification] = None,
    ) -> CooperationResult:
        """Run the task through a cooperation pattern (v0.2 path)."""
        pat = self.get_pattern(pattern)
        result = await pat.execute(
            task, self.router, self.registry, budget=budget,
        )
        # Stamp the intent on the metadata so callers can see which path ran
        result.metadata["intent"] = "model_call"
        if classification is not None:
            result.metadata["classification_reason"] = classification.reason
        return result


def _model_to_dict(model) -> dict:
    """Convert a ModelInfo to a JSON-friendly dict."""
    return {
        "provider": model.provider_name,
        "model_id": model.model_id,
        "tier": model.tier.value,
        "context_window": model.context_window,
        "cost_per_1m_input": model.cost_per_1m_input,
        "cost_per_1m_output": model.cost_per_1m_output,
        "terminal_bench_score": model.terminal_bench_score,
        "accepts_images": model.accepts_images,
        "notes": model.notes,
    }


__all__ = [
    "AriaAgent",
    "Intent",
    "IntentClassification",
    "_PATTERN_REGISTRY",
    "_TOOL_KEYWORDS",
]
