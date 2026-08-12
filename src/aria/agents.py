"""The ARIA agent — reason / route / approve / act loop.

``AriaAgent.run()`` orchestrates a single pass:

1. Persist the user query to memory.
2. Route the query to a tool (LLM router with keyword fallback, or pure keyword).
3. Check the tool's permission level against the approval gate. In approval-gated
   mode a risky tool yields a *pending* approval and the run pauses.
4. Execute the tool (validating arguments via its Pydantic schema), emitting a
   trace span and recording cost/latency.
5. Store the result in memory and return a structured ``RunResult``.

It keeps the simple surface: ``AriaAgent(registry, gate).run(query)``
returns a plain string (used by the original tests and the demo), while
``run_structured`` exposes the full result for the API.
"""

import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from .approvals import ApprovalGate
from .costs import CostTracker
from .memory import AgentMemory
from .routing import KeywordRouter, RouteDecision
from .store import ApprovalStatus
from .tools import ToolRegistry
from .tracing import TraceLog

if TYPE_CHECKING:
    from .skills import SkillSession


@dataclass
class RunResult:
    """Structured outcome of an agent run."""

    run_id: str
    query: str
    response: str
    status: str  # completed | pending_approval | blocked | error
    mode: str
    route: Optional[str] = None
    approval: Optional[Dict[str, Any]] = None
    trace: Dict[str, Any] = field(default_factory=dict)
    cost: Dict[str, Any] = field(default_factory=dict)
    skill_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "response": self.response,
            "status": self.status,
            "mode": self.mode,
            "route": self.route,
            "approval": self.approval,
            "trace": self.trace,
            "cost": self.cost,
            "skill_context": self.skill_context,
        }


class AriaAgent:
    """Runs the central reason-and-act loop with tool execution constraints."""

    def __init__(
        self,
        registry: ToolRegistry,
        approval_gate: ApprovalGate,
        max_steps: int = 5,
        router: Optional[Any] = None,
        memory: Optional[Any] = None,
        mode: Optional[str] = None,
        skill_session: Optional["SkillSession"] = None,
    ):
        self.registry = registry
        self.approval_gate = approval_gate
        self.max_steps = max_steps
        self.memory = memory or AgentMemory()
        # Default router is deterministic keyword routing (offline, no keys).
        self.router = router or KeywordRouter(tool_names=registry.names())
        self.mode = mode or approval_gate.mode
        self.skill_session = skill_session

    # --- public API ---------------------------------------------------------
    def run(self, user_query: str, trace=None, cost_tracker=None) -> str:
        """Backward-compatible entrypoint returning the response string."""
        result = self.run_structured(user_query, trace=trace, cost_tracker=cost_tracker)
        return result.response

    def run_structured(
        self,
        user_query: str,
        run_id: Optional[str] = None,
        trace: Optional[TraceLog] = None,
        cost_tracker: Optional[CostTracker] = None,
    ) -> RunResult:
        import uuid

        run_id = run_id or uuid.uuid4().hex[:8]
        trace = trace or TraceLog()
        cost_tracker = cost_tracker or CostTracker()

        logger.info("Agent run {} received: {}", run_id, user_query)
        self.memory.add_message("user", user_query)
        trace.add_reasoning(f"Processing query: {user_query}")
        base_context = self.memory.get_context(limit=6)
        context = base_context
        route_query = user_query
        if self.skill_session is not None:
            prepared = self.skill_session.prepare_turn(user_query, context)
            route_query = prepared.query
            context = prepared.context
        decision = self._route(route_query, context, cost_tracker)
        trace.add_decision(
            "route",
            f"tool={decision.tool} via {decision.strategy}",
            attributes={
                "tool": decision.tool,
                "strategy": decision.strategy,
                "rationale": decision.rationale,
            },
        )

        if not decision.is_tool:
            # An LLM routing request may already have consumed the skill-enriched
            # context. Keep provider delivery exactly once per turn by giving a
            # follow-up direct-response request only the base conversation.
            response_context = (
                base_context if decision.context_consumed else context
            )
            response = self._generate_response(
                user_query, response_context, cost_tracker
            )
            self.memory.add_message("system", response)
            return self._finish(
                run_id, user_query, response, "completed", decision, trace, cost_tracker
            )

        # Permission / approval check.
        try:
            requires_approval = self.registry.requires_approval(decision.tool)
        except KeyError:
            requires_approval = False
        gate = self.approval_gate.evaluate(
            decision.tool,
            decision.arguments,
            requires_approval=requires_approval,
            run_id=run_id,
        )

        if gate["decision"] == ApprovalStatus.PENDING.value:
            approval = gate["approval"]
            trace.add_decision(
                "approval_pending",
                f"{decision.tool} requires approval ({approval['id']})",
                attributes={"approval_id": approval["id"]},
            )
            response = (
                f"Action '{decision.tool}' requires approval. "
                f"Pending approval id: {approval['id']}."
            )
            self.memory.add_message("system", response)
            return self._finish(
                run_id,
                user_query,
                response,
                "pending_approval",
                decision,
                trace,
                cost_tracker,
                approval=approval,
            )

        # Execute the tool.
        response, status = self._execute_tool(decision, trace)
        self.memory.add_message("system", response)
        return self._finish(
            run_id, user_query, response, status, decision, trace, cost_tracker
        )

    def execute_approved(
        self,
        action: str,
        arguments: Dict[str, Any],
        trace: Optional[TraceLog] = None,
    ) -> str:
        """Execute a tool that was approved out-of-band (via the API)."""
        trace = trace or TraceLog()
        decision = RouteDecision(tool=action, arguments=arguments, strategy="approved")
        response, _ = self._execute_tool(decision, trace)
        return response

    # --- internals ----------------------------------------------------------
    def _route(self, query, context, cost_tracker) -> RouteDecision:
        try:
            # LLMRouter accepts a cost_tracker; KeywordRouter does not.
            return self.router.route(query, context, cost_tracker=cost_tracker)
        except TypeError:
            return self.router.route(query, context)

    def _execute_tool(self, decision: RouteDecision, trace: TraceLog):
        start = time.perf_counter()
        try:
            result = self.registry.call_tool(decision.tool, decision.arguments)
            latency = (time.perf_counter() - start) * 1000.0
            trace.add_tool_call(
                decision.tool, decision.arguments, result, latency, status="ok"
            )
            return str(result), "completed"
        except KeyError:
            latency = (time.perf_counter() - start) * 1000.0
            trace.add_tool_call(
                decision.tool,
                decision.arguments,
                "tool not found",
                latency,
                status="error",
            )
            logger.error("Tool not found: {}", decision.tool)
            return f"Error: Tool '{decision.tool}' not available.", "error"
        except Exception as exc:  # noqa: BLE001 - surface as a structured error
            latency = (time.perf_counter() - start) * 1000.0
            trace.add_tool_call(
                decision.tool,
                decision.arguments,
                f"error: {exc}",
                latency,
                status="error",
            )
            logger.error("Tool '{}' failed: {}", decision.tool, exc)
            return f"Error executing '{decision.tool}': {exc}", "error"

    def _generate_response(
        self, query: str, context: List[dict], cost_tracker: CostTracker
    ) -> str:
        client = getattr(self.router, "llm_client", None)
        if client is not None:
            try:
                result = client.generate(
                    "gpt-4o-mini",
                    "Follow the supplied conversation context, including system "
                    f"instructions. Context: {json.dumps(context, ensure_ascii=False)}. "
                    f"Respond to: {query}",
                    mocked_response="I understand your request. Let me help with that.",
                )
                telemetry = result.get("telemetry", {})
                cost_tracker.record_call(
                    "gpt-4o-mini",
                    int(telemetry.get("input_tokens", 0)),
                    int(telemetry.get("output_tokens", 0)),
                    float(telemetry.get("latency_ms", 0.0)),
                )
                return result["response"]
            except Exception:  # noqa: BLE001 - fall through to canned reply
                pass
        return "I processed your request but no tool was matched."

    def _finish(
        self,
        run_id,
        query,
        response,
        status,
        decision,
        trace,
        cost_tracker,
        approval=None,
    ) -> RunResult:
        skill_context = None
        if self.skill_session is not None:
            skill_context = self.skill_session.report().to_dict()
        return RunResult(
            run_id=run_id,
            query=query,
            response=response,
            status=status,
            mode=self.mode,
            route=decision.strategy if decision else None,
            approval=approval,
            trace=trace.summary(),
            cost=cost_tracker.summary(),
            skill_context=skill_context,
        )
