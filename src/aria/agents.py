"""Public ARIA agent facade backed by the internal execution engine.

The facade preserves the original ``AriaAgent`` and ``RunResult`` contracts;
planning, safety, retry, rate-limit, streaming, and replay behavior lives in
``aria.internal.core.engine.AgentEngine``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

from .approvals import ApprovalGate
from .costs import CostTracker
from .internal.core.contracts import ReplayResult, RunEvent
from .internal.core.engine import AgentEngine
from .internal.core.rate_limit import FixedWindowRateLimiter
from .internal.core.retry import RetryPolicy
from .memory import AgentMemory
from .routing import KeywordRouter, RouteDecision
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
    events: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
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
        if self.events is not None:
            data["events"] = self.events
        return data


class AriaAgent:
    """Compatibility facade for the canonical ARIA execution engine."""

    def __init__(
        self,
        registry: ToolRegistry,
        approval_gate: ApprovalGate,
        max_steps: int = 5,
        router: Optional[Any] = None,
        memory: Optional[Any] = None,
        mode: Optional[str] = None,
        skill_session: Optional["SkillSession"] = None,
        *,
        planning_mode: str = "single",
        safety_mode: str = "warn",
        retry_policies: Optional[dict[str, RetryPolicy]] = None,
        rate_limiter: Optional[FixedWindowRateLimiter] = None,
        session_id: str = "default",
    ):
        self.registry = registry
        self.approval_gate = approval_gate
        self.max_steps = max_steps
        self.memory = memory or AgentMemory()
        self.router = router or KeywordRouter(tool_names=registry.names())
        self.mode = mode or approval_gate.mode
        self.skill_session = skill_session
        self.engine = AgentEngine(
            registry,
            approval_gate,
            router=self.router,
            memory=self.memory,
            max_steps=max_steps,
            mode=self.mode,
            skill_session=skill_session,
            planning_mode=planning_mode,
            safety_mode=safety_mode,
            retry_policies=retry_policies,
            rate_limiter=rate_limiter,
            session_id=session_id,
        )

    def run(self, user_query: str, trace=None, cost_tracker=None) -> str:
        """Backward-compatible entrypoint returning only the response string."""
        return self.run_structured(
            user_query, trace=trace, cost_tracker=cost_tracker
        ).response

    def run_structured(
        self,
        user_query: str,
        run_id: Optional[str] = None,
        trace: Optional[TraceLog] = None,
        cost_tracker: Optional[CostTracker] = None,
    ) -> RunResult:
        import uuid

        resolved_run_id = run_id or uuid.uuid4().hex[:8]
        resolved_cost = cost_tracker or CostTracker()
        outcome = self.engine.run_structured(
            user_query,
            run_id=resolved_run_id,
            trace=trace,
            cost_tracker=resolved_cost,
        )
        return RunResult(
            run_id=resolved_run_id,
            query=user_query,
            response=outcome.response,
            status=outcome.status,
            mode=self.mode,
            route=outcome.decision.strategy if outcome.decision else None,
            approval=outcome.approval,
            trace=outcome.trace,
            cost=outcome.cost,
            skill_context=outcome.skill_context,
        )

    def execute_approved(
        self,
        action: str,
        arguments: Dict[str, Any],
        trace: Optional[TraceLog] = None,
    ) -> str:
        """Execute a tool approved out-of-band through the existing API."""
        return self.engine.execute_approved(action, arguments, trace=trace)

    def replay(
        self,
        trace_summary: Dict[str, Any],
        *,
        dry_run: bool = True,
        run_id: str = "replay",
    ) -> ReplayResult:
        return self.engine.replay(trace_summary, dry_run=dry_run, run_id=run_id)

    def stream_events(self, user_query: str, **kwargs: Any) -> Iterable[RunEvent]:
        """Yield ordered events for the SSE facade without changing chat output."""
        import uuid

        cost_tracker = kwargs.pop("cost_tracker", None) or CostTracker()
        trace = kwargs.pop("trace", None)
        run_id = kwargs.pop("run_id", None) or uuid.uuid4().hex[:8]
        yield from self.engine.stream_events(
            user_query,
            run_id=run_id,
            trace=trace,
            cost_tracker=cost_tracker,
            **kwargs,
        )

    # Private compatibility helpers retained for existing integrations/tests.
    def _route(self, query, context, cost_tracker):
        router: Any = self.router
        try:
            return router.route(query, context, cost_tracker=cost_tracker)
        except TypeError:
            return router.route(query, context)

    def _execute_tool(self, decision: RouteDecision, trace: TraceLog):
        return self.engine._execute_tool(decision, trace)
