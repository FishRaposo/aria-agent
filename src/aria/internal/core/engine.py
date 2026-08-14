"""ARIA's canonical reason/plan/approve/act execution engine."""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, cast

from loguru import logger

from ...approvals import ApprovalGate
from ...routing import RouteDecision
from ...store import ApprovalStatus
from ...tools import ToolRegistry
from ...tracing import TraceLog
from .contracts import (
    ReplayResult,
    RunEvent,
    RunEventType,
)
from .rate_limit import FixedWindowRateLimiter
from .retry import RetryPolicy, execute_with_retry
from .safety import SafetyClassifier


@dataclass
class EngineOutcome:
    response: str
    status: str
    decision: Optional[RouteDecision]
    approval: Optional[Dict[str, Any]]
    trace: Dict[str, Any]
    cost: Dict[str, Any]
    skill_context: Optional[Dict[str, Any]]


class AgentEngine:
    """Own the execution policy while keeping legacy ARIA facades stable."""

    _SPLIT_RE = re.compile(r"\s+then\s+|\s*;\s*", re.IGNORECASE)

    def __init__(
        self,
        registry: ToolRegistry,
        approval_gate: ApprovalGate,
        *,
        router: Any,
        memory: Any,
        max_steps: int = 5,
        mode: str = "free_running",
        skill_session: Any = None,
        planning_mode: str = "single",
        safety_mode: str = "warn",
        retry_policies: Optional[dict[str, RetryPolicy]] = None,
        rate_limiter: Optional[FixedWindowRateLimiter] = None,
        session_id: str = "default",
    ) -> None:
        if planning_mode not in {"single", "multi"}:
            raise ValueError("planning_mode must be single or multi")
        self.registry = registry
        self.approval_gate = approval_gate
        self.router = router
        self.memory = memory
        self.max_steps = max_steps
        self.mode = mode
        self.skill_session = skill_session
        self.planning_mode = planning_mode
        self.safety = SafetyClassifier(policy=safety_mode)
        self.retry_policies = retry_policies or {}
        self.rate_limiter = rate_limiter
        self.session_id = session_id

    def run_structured(
        self,
        user_query: str,
        *,
        run_id: Optional[str] = None,
        trace: Optional[TraceLog] = None,
        cost_tracker: Any,
        event_sink: Optional[list[RunEvent]] = None,
    ) -> EngineOutcome:
        run_id = run_id or uuid.uuid4().hex[:8]
        trace = trace or TraceLog()
        self._sequence = 0
        self._event_sink = event_sink
        self._emit(
            RunEventType.REASONING, {"content": f"Processing query: {user_query}"}
        )
        logger.info("Agent run {} received: {}", run_id, user_query)
        self.memory.add_message("user", user_query)

        base_context = self.memory.get_context(limit=6)
        context = base_context
        route_query = user_query
        context_consumed = False
        if self.skill_session is not None:
            prepared = self.skill_session.prepare_turn(user_query, context)
            route_query = prepared.query
            context = prepared.context

        query_assessment = self.safety.assess(
            user_query,
            context=[message.get("content", "") for message in context],
        )
        if query_assessment.matches:
            trace.add_decision(
                "safety", query_assessment.reason, query_assessment.to_dict()
            )
            self._emit(RunEventType.DECISION, {"safety": query_assessment.to_dict()})
        if query_assessment.action == "block":
            blocked = f"Blocked by safety policy: {query_assessment.reason}."
            self._emit(RunEventType.ERROR, {"reason": query_assessment.reason})
            self._emit(RunEventType.COMPLETE, {"status": "blocked"})
            return self._finish(
                user_query,
                "blocked",
                RouteDecision(
                    tool=None, strategy="safety", rationale=query_assessment.reason
                ),
                trace,
                cost_tracker,
                blocked,
                None,
            )

        decisions, context_consumed = self._plan(route_query, context, cost_tracker)
        first_decision = (
            decisions[0]
            if decisions
            else RouteDecision(tool=None, strategy="keyword", rationale="no plan step")
        )
        if not decisions:
            trace.add_decision(
                "route",
                "tool=None via no plan step",
                attributes={"tool": None, "strategy": "keyword"},
            )
            self._emit(RunEventType.DECISION, {"tool": None, "strategy": "keyword"})
            response_context = base_context if context_consumed else context
            response = self._generate_response(
                user_query, response_context, cost_tracker
            )
            self.memory.add_message("system", response)
            self._emit(RunEventType.COMPLETE, {"status": "completed"})
            return self._finish(
                user_query,
                "completed",
                first_decision,
                trace,
                cost_tracker,
                response,
                None,
            )

        last_response = ""
        last_status = "completed"
        approval: Optional[Dict[str, Any]] = None
        for index, decision in enumerate(decisions, start=1):
            tool_name = decision.tool
            if tool_name is None:
                continue
            trace.add_decision(
                "route" if index == 1 else f"route.step_{index}",
                f"tool={decision.tool} via {decision.strategy}",
                attributes={
                    "tool": decision.tool,
                    "strategy": decision.strategy,
                    "rationale": decision.rationale,
                    "step": index,
                },
            )
            self._emit(
                RunEventType.DECISION,
                {"tool": decision.tool, "strategy": decision.strategy, "step": index},
            )

            assessment = self.safety.assess(
                user_query,
                context=[message.get("content", "") for message in context],
                arguments=decision.arguments,
            )
            if assessment.matches:
                trace.add_decision("safety", assessment.reason, assessment.to_dict())
                self._emit(RunEventType.DECISION, {"safety": assessment.to_dict()})
            if assessment.action == "block":
                last_response = f"Blocked by safety policy: {assessment.reason}."
                last_status = "blocked"
                self._emit(RunEventType.ERROR, {"reason": assessment.reason})
                self._emit(RunEventType.COMPLETE, {"status": last_status})
                return self._finish(
                    user_query,
                    last_status,
                    first_decision,
                    trace,
                    cost_tracker,
                    last_response,
                    None,
                )

            if self.rate_limiter is not None:
                rate = self.rate_limiter.allow(self.session_id, tool_name)
                if not rate.allowed:
                    last_response = (
                        f"Blocked by rate limit for '{tool_name}'; "
                        f"retry after {rate.retry_after_seconds:.3f}s."
                    )
                    trace.add_decision("rate_limit", last_response, rate.to_dict())
                    self._emit(RunEventType.ERROR, {"rate_limit": rate.to_dict()})
                    self._emit(RunEventType.COMPLETE, {"status": "blocked"})
                    return self._finish(
                        user_query,
                        "blocked",
                        first_decision,
                        trace,
                        cost_tracker,
                        last_response,
                        None,
                    )

            try:
                requires_approval = self.registry.requires_approval(tool_name)
            except KeyError:
                requires_approval = False
            gate = self.approval_gate.evaluate(
                tool_name,
                decision.arguments,
                requires_approval=requires_approval,
                run_id=run_id,
            )
            if gate["decision"] == ApprovalStatus.PENDING.value:
                approval = cast(Dict[str, Any], gate.get("approval") or {})
                approval_id = str(approval["id"])
                trace.add_decision(
                    "approval_pending",
                    f"{tool_name} requires approval ({approval_id})",
                    attributes={"approval_id": approval_id, "step": index},
                )
                self._emit(RunEventType.APPROVAL, {"approval": approval, "step": index})
                last_response = (
                    f"Action '{tool_name}' requires approval. "
                    f"Pending approval id: {approval_id}."
                )
                self.memory.add_message("system", last_response)
                self._emit(RunEventType.COMPLETE, {"status": "pending_approval"})
                return self._finish(
                    user_query,
                    "pending_approval",
                    first_decision,
                    trace,
                    cost_tracker,
                    last_response,
                    approval,
                )

            last_response, last_status = self._execute_tool(decision, trace)
            self._emit(
                RunEventType.TOOL,
                {"tool": tool_name, "status": last_status, "step": index},
            )
            if last_status != "completed":
                self._emit(RunEventType.COMPLETE, {"status": last_status})
                self.memory.add_message("system", last_response)
                return self._finish(
                    user_query,
                    last_status,
                    first_decision,
                    trace,
                    cost_tracker,
                    last_response,
                    None,
                )

        self.memory.add_message("system", last_response)
        self._emit(RunEventType.COMPLETE, {"status": last_status})
        return self._finish(
            user_query,
            last_status,
            first_decision,
            trace,
            cost_tracker,
            last_response,
            approval,
        )

    def stream_events(self, user_query: str, **kwargs: Any) -> Iterable[RunEvent]:
        events: list[RunEvent] = []
        self.run_structured(user_query, event_sink=events, **kwargs)
        yield from events

    def execute_approved(
        self,
        action: str,
        arguments: Dict[str, Any],
        *,
        trace: Optional[TraceLog] = None,
    ) -> str:
        trace = trace or TraceLog()
        return self._execute_tool(
            RouteDecision(tool=action, arguments=arguments, strategy="approved"), trace
        )[0]

    def replay(
        self,
        trace_summary: Dict[str, Any],
        *,
        run_id: str,
        dry_run: bool = True,
    ) -> ReplayResult:
        steps = tuple(
            {
                "step": entry.get("step"),
                "tool": entry.get("tool"),
                "params": dict(entry.get("params") or {}),
                "recorded_result": entry.get("result"),
                "replayed": not dry_run,
            }
            for entry in trace_summary.get("entries", [])
            if entry.get("type") == "tool_call"
        )
        return ReplayResult(
            run_id=run_id,
            dry_run=dry_run,
            steps=steps,
            side_effects_executed=False,
            status="completed",
        )

    def _plan(
        self, query: str, context: list[dict[str, Any]], cost_tracker: Any
    ) -> tuple[list[RouteDecision], bool]:
        queries = [query]
        if self.planning_mode == "multi":
            queries = [
                part.strip() for part in self._SPLIT_RE.split(query) if part.strip()
            ]
            queries = queries[: max(1, self.max_steps)]
        decisions: list[RouteDecision] = []
        context_consumed = False
        for part in queries:
            try:
                decision = self.router.route(part, context, cost_tracker=cost_tracker)
            except TypeError:
                decision = self.router.route(part, context)
            context_consumed = context_consumed or bool(
                getattr(decision, "context_consumed", False)
            )
            if decision.is_tool:
                decisions.append(decision)
            elif self.planning_mode == "single":
                break
        return decisions, context_consumed

    def _execute_tool(
        self, decision: RouteDecision, trace: TraceLog
    ) -> tuple[str, str]:
        start = time.perf_counter()
        tool_name = decision.tool
        if tool_name is None:
            return "", "error"
        policy = self.retry_policies.get(tool_name, RetryPolicy())
        # Retrying a side-effecting tool could duplicate the effect.  Only
        # explicitly safe/idempotent tools inherit configured retry attempts.
        try:
            if self.registry.requires_approval(tool_name):
                policy = RetryPolicy()
        except KeyError:
            pass

        def operation() -> Any:
            return self.registry.call_tool(tool_name, decision.arguments)

        try:
            outcome = execute_with_retry(operation, policy, sleep=time.sleep)
            latency = (time.perf_counter() - start) * 1000.0
            trace.add_tool_call(
                tool_name,
                decision.arguments,
                outcome.value,
                latency,
                status="ok",
            )
            return str(outcome.value), "completed"
        except KeyError:
            latency = (time.perf_counter() - start) * 1000.0
            trace.add_tool_call(
                tool_name,
                decision.arguments,
                "tool not found",
                latency,
                status="error",
            )
            logger.error("Tool not found: {}", tool_name)
            return f"Error: Tool '{tool_name}' not available.", "error"
        except Exception as exc:  # noqa: BLE001 - structured agent failure
            latency = (time.perf_counter() - start) * 1000.0
            trace.add_tool_call(
                tool_name,
                decision.arguments,
                f"error: {exc}",
                latency,
                status="error",
            )
            logger.error("Tool '{}' failed: {}", tool_name, exc)
            return f"Error executing '{tool_name}': {exc}", "error"

    def _generate_response(
        self, query: str, context: List[dict], cost_tracker: Any
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
        query: str,
        status: str,
        decision: RouteDecision,
        trace: TraceLog,
        cost_tracker: Any,
        response: str,
        approval: Optional[Dict[str, Any]],
    ) -> EngineOutcome:
        skill_context = (
            self.skill_session.report().to_dict()
            if self.skill_session is not None
            else None
        )
        return EngineOutcome(
            response=response,
            status=status,
            decision=decision,
            approval=approval,
            trace=trace.summary(),
            cost=cost_tracker.summary(),
            skill_context=skill_context,
        )

    def _emit(self, event_type: RunEventType, payload: dict[str, Any]) -> None:
        if self._event_sink is None:
            return
        self._sequence += 1
        self._event_sink.append(
            RunEvent(sequence=self._sequence, event_type=event_type, payload=payload)
        )
