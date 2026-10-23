"""FastAPI gateway for the ARIA agent framework.

Wires the agent loop, tool registry, approval queue, persistent stores, cost
tracking, and tracing behind a small REST surface. Everything runs offline by
default: on startup the DB-availability probe selects persistent (PostgreSQL) or
in-memory stores transparently, so the service boots with no database, no Redis,
and no API keys.

Endpoints a dashboard would need:
  POST /agent/chat                 run the agent on a message
  GET  /agent/runs                 list recent runs
  GET  /agent/runs/{id}            fetch a run (with full trace + cost)
  GET  /agent/trace/{id}           fetch just the trace (compat alias)
  GET  /skills                    metadata and saved run skill context
  GET  /agent/memory              session-isolated conversation messages
  GET  /approvals                  list approvals (optional ?status=)
  POST /approvals/{id}/approve     approve a pending approval (executes the tool)
  POST /approvals/{id}/reject      reject a pending approval
  GET  /tools, GET /tools/{name}   tool registry introspection
  GET  /health                     dependency health
"""

import json
import threading
import time
import uuid
from copy import deepcopy
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from aria.internal.vendor_core.errors import (
    BaseApplicationError,
    application_error_handler,
)
from aria.internal.vendor_core.health import check_health
from aria.internal.vendor_core.logging import setup_logging

from . import db as db_module
from .agents import AriaAgent
from .approvals import ApprovalGate
from .config import AppConfig
from .costs import CostTracker
from .internal.core.engine import ApprovalExecutionDenied
from .internal.core.memory import LocalVectorIndex
from .internal.core.rate_limit import FixedWindowRateLimiter
from .internal.core.retry import RetryPolicy
from .internal.core.sweeper import ApprovalSweeper
from .llm_client import AgentLLMClient
from .memory import get_memory
from .routing import build_router
from .store import ApprovalStatus
from .tools import build_default_registry
from .tracing import TraceLog

config = AppConfig()
setup_logging(level=config.LOG_LEVEL, service_name=config.APP_NAME)

app = FastAPI(title=config.APP_NAME, version="1.0.0")
if config.CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ALLOWED_ORIGINS.split(","),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
app.add_exception_handler(BaseApplicationError, application_error_handler)  # type: ignore[arg-type]

# --- store wiring (DB when available, else in-memory) -----------------------
db_module.check_db()
run_store = db_module.build_run_store()
task_store = db_module.build_task_store()
approval_store = db_module.build_approval_store(timeout=config.APPROVAL_TIMEOUT_SECONDS)

# --- agent wiring -----------------------------------------------------------
_api_keys = {}
if config.OPENAI_API_KEY:
    _api_keys["openai"] = config.OPENAI_API_KEY.get_secret_value()
if config.ANTHROPIC_API_KEY:
    _api_keys["anthropic"] = config.ANTHROPIC_API_KEY.get_secret_value()

llm_client = AgentLLMClient(api_keys=_api_keys)
registry = build_default_registry(task_store=task_store)
router = build_router(config.AGENT_ROUTING, llm_client=llm_client)
gate = ApprovalGate(enabled=True, mode=config.AGENT_MODE, store=approval_store)
sweeper = ApprovalSweeper(approval_store)


def _retry_policies() -> dict[str, RetryPolicy]:
    try:
        raw = json.loads(config.ARIA_TOOL_RETRY_POLICIES or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    policies = {}
    for tool, value in raw.items():
        if isinstance(value, dict):
            try:
                policies[tool] = RetryPolicy(
                    max_attempts=int(value.get("max_attempts", 1)),
                    backoff_seconds=float(value.get("backoff_seconds", 0.0)),
                )
            except (TypeError, ValueError):
                continue
    return policies


rate_limiter = (
    FixedWindowRateLimiter(
        limit=config.ARIA_RATE_LIMIT_PER_TOOL,
        window_seconds=config.ARIA_RATE_LIMIT_WINDOW_SECONDS,
        clock=time.time,
    )
    if config.ARIA_RATE_LIMIT_PER_TOOL > 0
    else None
)

# Keep offline conversation memory stable across requests.  The DB-backed
# implementation remains the source of truth when a database is available;
# this cache only gives the credential-free demo the same multi-turn behavior.
_offline_memories: dict[str, Any] = {}
_memory_lock = threading.Lock()


def _memory_for_session(session_id: str) -> Any:
    if db_module.db_available and db_module.db_manager is not None:
        return get_memory(session_id)
    with _memory_lock:
        if session_id not in _offline_memories:
            _offline_memories[session_id] = get_memory(session_id)
        return _offline_memories[session_id]


def _build_agent(mode: str, session_id: str) -> AriaAgent:
    """Construct a per-request agent bound to the active stores."""
    from .skill_runtime import create_api_skill_session

    request_gate = ApprovalGate(enabled=True, mode=mode, store=approval_store)
    return AriaAgent(
        registry,
        request_gate,
        max_steps=config.AGENT_MAX_STEPS,
        router=router,
        memory=_memory_for_session(session_id),
        mode=mode,
        planning_mode=config.ARIA_PLANNING_MODE,
        safety_mode=config.ARIA_SAFETY_MODE,
        retry_policies=_retry_policies(),
        rate_limiter=rate_limiter,
        session_id=session_id,
        skill_session=create_api_skill_session(
            planning_mode=config.ARIA_PLANNING_MODE, max_steps=config.AGENT_MAX_STEPS
        ),
    )


# Health needs a db/redis manager pair; reuse the probe's manager when present.
class _OfflineRedis:
    def ping(self) -> bool:
        return False


redis_manager = _OfflineRedis()


# --- request/response models ------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: str = Field("default", min_length=1, max_length=64)
    mode: Optional[str] = None  # free_running | approval_gated


class DecisionRequest(BaseModel):
    reason: Optional[str] = None


class ReplayRequest(BaseModel):
    dry_run: bool = True


def _request_mode(requested: Optional[str]) -> str:
    if (
        config.AGENT_MODE == "approval_gated"
        and config.ARIA_SAFETY_MODE == "block"
        and requested is not None
        and requested != "approval_gated"
    ):
        raise HTTPException(409, "The strict execution profile cannot be downgraded")
    return requested or config.AGENT_MODE


def _approval_for_run(run: dict[str, Any]) -> Optional[dict[str, Any]]:
    approval_id = run.get("approval_id")
    if approval_id:
        approval = approval_store.get(approval_id)
        return approval if approval and approval.get("run_id") == run["id"] else None
    return None


def _reconcile_run(run: dict[str, Any]) -> dict[str, Any]:
    """Project durable authority into a view without retrying any tool."""
    view = deepcopy(run)
    view.setdefault("session_id", None)
    view.setdefault("skill_context", None)
    approval = _approval_for_run(run)
    view["approval"] = approval
    if approval is None:
        return view
    execution = approval.get("execution_status")
    status = approval["status"]
    final = None
    if execution == "completed":
        view["status"] = "completed"
        view["response"] = (
            approval.get("execution_result")
            or "Approved action completed; result unavailable."
        )
        final = "completed"
    elif execution == "failed":
        view["status"] = "error"
        view["response"] = (
            approval.get("execution_result")
            or "Approved action failed; inspect the execution trace."
        )
        final = "failed"
    elif execution == "claimed":
        view["status"] = "pending_approval"
        view["response"] = (
            "Execution outcome unconfirmed. The action will not be retried automatically."
        )
    elif status in {"rejected", "expired"}:
        view["status"] = "blocked"
        view["response"] = f"Approval {status}. No action was executed."
        final = status
    execution_trace = approval.get("execution_trace")
    if execution_trace:
        trace = deepcopy(view.get("trace") or {})
        entries = list(trace.get("entries") or [])
        for entry in execution_trace.get("entries") or []:
            entries.append({**entry, "step": len(entries) + 1})
        trace["entries"] = entries
        trace["total_steps"] = len(entries)
        trace["spans"] = list(trace.get("spans") or []) + list(
            execution_trace.get("spans") or []
        )
        trace["approval_execution"] = deepcopy(execution_trace)
        view["trace"] = trace
    if final and run.get("session_id") is not None:
        memory = _memory_for_session(run["session_id"])
        memory.add_message_once(
            "system",
            f"Approval outcome {final} for run {run['id']}: {view['response']}",
            f"approval:{approval['id']}:{final}",
        )
    return view


def _reconcile_session(session_id: str) -> None:
    # Read every saved run in this session; immutable event keys make replay
    # harmless after restart, even if the process died before updating memory.
    for run in reversed(run_store.list(limit=1_000_000, session_id=session_id)):
        if run.get("approval_id"):
            _reconcile_run(run)


def _save_run(
    result: Any,
    session_id: str,
    *,
    run_id: Optional[str] = None,
    query: Optional[str] = None,
    mode: Optional[str] = None,
) -> dict[str, Any]:
    approval = result.approval
    run = {
        "id": run_id or result.run_id,
        "query": query if query is not None else result.query,
        "response": result.response,
        "mode": mode or result.mode,
        "status": result.status,
        "route": (result.decision.strategy if result.decision else None)
        if run_id
        else result.route,
        "trace": result.trace,
        "cost": result.cost,
        "session_id": session_id,
        "skill_context": result.skill_context,
        "approval_id": approval.get("id") if approval else None,
        "created_at": time.time(),
    }
    run_store.save(run)
    return _reconcile_run(run)


# --- endpoints --------------------------------------------------------------
@app.post("/agent/chat")
def chat(req: ChatRequest):
    mode = _request_mode(req.mode)
    _reconcile_session(req.session_id)
    agent = _build_agent(mode, req.session_id)
    run_id = uuid.uuid4().hex[:8]
    result = agent.run_structured(
        req.message, run_id=run_id, trace=TraceLog(), cost_tracker=CostTracker()
    )
    saved = _save_run(result, req.session_id)
    payload = result.to_dict()
    payload.update(
        {
            key: saved[key]
            for key in ("session_id", "skill_context", "approval", "status", "response")
        }
    )
    payload["reply"] = saved["response"]  # back-compat alias
    return payload


@app.post("/agent/chat/stream")
def chat_stream(req: ChatRequest):
    """Emit the same engine events as ``/agent/chat`` using Server-Sent Events."""

    mode = _request_mode(req.mode)
    _reconcile_session(req.session_id)
    agent = _build_agent(mode, req.session_id)
    run_id = uuid.uuid4().hex[:8]

    def events():
        event_buffer: list[Any] = []
        outcome = agent.engine.run_structured(
            req.message,
            run_id=run_id,
            trace=TraceLog(),
            cost_tracker=CostTracker(),
            event_sink=event_buffer,
        )
        _save_run(outcome, req.session_id, run_id=run_id, query=req.message, mode=mode)
        for event in event_buffer:
            yield f"event: {event.event_type.value}\ndata: {json.dumps(event.to_dict(), sort_keys=True)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/agent/runs")
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    session_id: Optional[str] = Query(None, min_length=1, max_length=64),
):
    return {
        "runs": [
            _reconcile_run(run)
            for run in run_store.list(limit=limit, session_id=session_id)
        ]
    }


@app.get("/agent/runs/{run_id}")
def get_run(run_id: str):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found")
    return _reconcile_run(run)


@app.get("/agent/trace/{run_id}")
def get_trace(run_id: str):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found")
    view = _reconcile_run(run)
    return {"run_id": run_id, "trace": view.get("trace"), "cost": view.get("cost")}


@app.post("/agent/runs/{run_id}/replay")
def replay_run(run_id: str, body: ReplayRequest | None = None):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found")
    request = body or ReplayRequest()
    agent = _build_agent(config.AGENT_MODE, "default")
    return agent.replay(
        run.get("trace") or {}, run_id=run_id, dry_run=request.dry_run
    ).to_dict()


@app.get("/skills")
def list_skills(
    session_id: str = Query("default", min_length=1, max_length=64),
    run_id: Optional[str] = None,
):
    from .skill_runtime import build_skills_snapshot

    run = None
    if run_id is not None:
        run = run_store.get(run_id)
        if run is None or run.get("session_id") != session_id:
            raise HTTPException(404, "Run not found in this session")
    else:
        runs = run_store.list(limit=1, session_id=session_id)
        run = runs[0] if runs else None
    return build_skills_snapshot(session_id=session_id, run=run)


@app.get("/agent/memory")
def list_memory(
    session_id: str = Query("default", min_length=1, max_length=64),
    limit: int = Query(50, ge=1, le=200),
):
    _reconcile_session(session_id)
    return {
        "session_id": session_id,
        "messages": _memory_for_session(session_id).get_context(limit=limit),
    }


@app.get("/agent/memory/search")
def search_memory(
    query: str = Query(..., min_length=1),
    session_id: str = Query("default", min_length=1, max_length=64),
    limit: int = Query(5, ge=1, le=50),
):
    _reconcile_session(session_id)
    memory = _memory_for_session(session_id)
    index = LocalVectorIndex()
    for index_number, message in enumerate(memory.get_context(), start=1):
        index.add(
            f"{session_id}:{index_number}",
            message.get("content", ""),
        )
    return {"matches": [match.to_dict() for match in index.search(query, limit=limit)]}


@app.get("/approvals")
def list_approvals(
    status: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None, min_length=1, max_length=64),
):
    if session_id is None:
        return {"approvals": approval_store.list(status=status)}
    approvals = []
    for run in run_store.list(limit=1_000_000, session_id=session_id):
        approval = _approval_for_run(run)
        if approval is not None and (status is None or approval["status"] == status):
            approvals.append(approval)
    approvals.sort(key=lambda approval: approval["expires_at"], reverse=True)
    return {"approvals": approvals[:100]}


@app.post("/approvals/sweep")
def sweep_approvals():
    """Run the optional local expiry sweep without requiring a broker."""

    if not config.ARIA_APPROVAL_SWEEPER_ENABLED:
        return {"enabled": False, "checked": 0, "expired": 0}
    result = sweeper.sweep()
    return {"enabled": True, **result}


@app.get("/approvals/{approval_id}")
def get_approval(approval_id: str):
    approval = approval_store.get(approval_id)
    if approval is None:
        raise HTTPException(404, f"Approval '{approval_id}' not found")
    return approval


@app.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, body: DecisionRequest | None = None):
    approval = approval_store.get(approval_id)
    if approval is None:
        raise HTTPException(404, f"Approval '{approval_id}' not found")
    if approval["status"] != ApprovalStatus.PENDING.value:
        raise HTTPException(
            409, f"Approval '{approval_id}' is already {approval['status']}"
        )
    reason = body.reason if body else None
    decided = approval_store.decide(approval_id, approved=True, reason=reason)
    if decided is None:
        raise HTTPException(404, f"Approval '{approval_id}' not found")
    # The approval may have expired between the PENDING check and decide(); only
    # execute the gated tool when it is actually approved, never a stale action.
    if decided["status"] != ApprovalStatus.APPROVED.value:
        return {"approval": decided}
    # Execute the now-approved tool and capture a trace.
    originating_run_id = decided.get("run_id")
    originating_run = run_store.get(originating_run_id) if originating_run_id else None
    session_id = originating_run.get("session_id") if originating_run else None
    agent = _build_agent(config.AGENT_MODE, session_id or "default")
    trace = TraceLog()
    try:
        result = agent.execute_approved(
            decided["action"],
            decided["parameters"],
            trace=trace,
            approval_id=approval_id,
            run_id=decided.get("run_id"),
        )
    except ApprovalExecutionDenied as exc:
        raise HTTPException(
            409, {"reason": str(exc), "trace": trace.summary()}
        ) from exc
    if originating_run:
        _reconcile_run(originating_run)
    return {
        "approval": approval_store.get(approval_id),
        "result": result,
        "trace": trace.summary(),
    }


@app.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, body: DecisionRequest | None = None):
    approval = approval_store.get(approval_id)
    if approval is None:
        raise HTTPException(404, f"Approval '{approval_id}' not found")
    if approval["status"] != ApprovalStatus.PENDING.value:
        raise HTTPException(
            409, f"Approval '{approval_id}' is already {approval['status']}"
        )
    reason = body.reason if body else None
    decided = approval_store.decide(approval_id, approved=False, reason=reason)
    if decided is not None and decided["status"] == ApprovalStatus.APPROVED.value:
        raise HTTPException(409, f"Approval '{approval_id}' is already approved")
    if decided and decided.get("run_id"):
        run = run_store.get(decided["run_id"])
        if run:
            _reconcile_run(run)
    return {"approval": decided}


@app.get("/tools")
def list_tools():
    return {"tools": registry.list_tools()}


@app.get("/tools/{name}")
def get_tool_schema(name: str):
    try:
        return {
            "name": name,
            "permission": registry.permission_for(name).value,
            "description": registry.descriptions.get(name, ""),
            "schema": registry.get_schema(name),
        }
    except KeyError as exc:
        raise HTTPException(404, f"Tool '{name}' not found") from exc


@app.get("/health")
def health_check():
    persistent = db_module.db_available and db_module.db_manager is not None
    if persistent:
        health = check_health(db_module.db_manager, redis_manager, config.APP_NAME)
    else:
        health = {
            "status": "degraded",
            "service": config.APP_NAME,
            "dependencies": {"database": "offline", "redis": "offline"},
        }
    strict = (
        config.AGENT_MODE == "approval_gated" and config.ARIA_SAFETY_MODE == "block"
    )
    persistence = db_module.db_manager.engine.dialect.name if persistent else "memory"
    from .skill_runtime import build_skills_snapshot

    try:
        available = bool(
            build_skills_snapshot(session_id="default", run=None)["catalog"]
        )
    except (OSError, ValueError):
        available = False
    health["runtime"] = {
        "agent_mode": config.AGENT_MODE,
        "allowed_modes": ["approval_gated"]
        if strict
        else ["free_running", "approval_gated"],
        "routing_mode": config.AGENT_ROUTING,
        "skill_selection_mode": "automatic",
        "persistence": persistence,
        "skills_available": available,
    }
    return health
