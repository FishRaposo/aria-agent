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
  GET  /approvals                  list approvals (optional ?status=)
  POST /approvals/{id}/approve     approve a pending approval (executes the tool)
  POST /approvals/{id}/reject      reject a pending approval
  GET  /tools, GET /tools/{name}   tool registry introspection
  GET  /health                     dependency health
"""

import json
import time
import uuid
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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


def _memory_for_session(session_id: str) -> Any:
    if db_module.db_available and db_module.db_manager is not None:
        return get_memory(session_id)
    if session_id not in _offline_memories:
        _offline_memories[session_id] = get_memory(session_id)
    return _offline_memories[session_id]


def _build_agent(mode: str, session_id: str) -> AriaAgent:
    """Construct a per-request agent bound to the active stores."""
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
    )


# Health needs a db/redis manager pair; reuse the probe's manager when present.
class _OfflineRedis:
    def ping(self) -> bool:
        return False


redis_manager = _OfflineRedis()


# --- request/response models ------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    mode: Optional[str] = None  # free_running | approval_gated


class DecisionRequest(BaseModel):
    reason: Optional[str] = None


class ReplayRequest(BaseModel):
    dry_run: bool = True


# --- endpoints --------------------------------------------------------------
@app.post("/agent/chat")
def chat(req: ChatRequest):
    mode = req.mode or config.AGENT_MODE
    agent = _build_agent(mode, req.session_id)
    run_id = uuid.uuid4().hex[:8]
    result = agent.run_structured(
        req.message, run_id=run_id, trace=TraceLog(), cost_tracker=CostTracker()
    )
    run_store.save(
        {
            "id": result.run_id,
            "query": result.query,
            "response": result.response,
            "mode": result.mode,
            "status": result.status,
            "route": result.route,
            "trace": result.trace,
            "cost": result.cost,
            "created_at": time.time(),
        }
    )
    payload = result.to_dict()
    payload["reply"] = result.response  # back-compat alias
    return payload


@app.post("/agent/chat/stream")
def chat_stream(req: ChatRequest):
    """Emit the same engine events as ``/agent/chat`` using Server-Sent Events."""

    mode = req.mode or config.AGENT_MODE
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
        run_store.save(
            {
                "id": run_id,
                "query": req.message,
                "response": outcome.response,
                "mode": mode,
                "status": outcome.status,
                "route": outcome.decision.strategy if outcome.decision else None,
                "trace": outcome.trace,
                "cost": outcome.cost,
                "created_at": time.time(),
            }
        )
        for event in event_buffer:
            yield f"event: {event.event_type.value}\ndata: {json.dumps(event.to_dict(), sort_keys=True)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.get("/agent/runs")
def list_runs(limit: int = Query(50, ge=1, le=200)):
    return {"runs": run_store.list(limit=limit)}


@app.get("/agent/runs/{run_id}")
def get_run(run_id: str):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found")
    return run


@app.get("/agent/trace/{run_id}")
def get_trace(run_id: str):
    run = run_store.get(run_id)
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found")
    return {"run_id": run_id, "trace": run.get("trace"), "cost": run.get("cost")}


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


@app.get("/agent/memory/search")
def search_memory(
    query: str = Query(..., min_length=1),
    session_id: str = Query("default", min_length=1),
    limit: int = Query(5, ge=1, le=50),
):
    memory = _memory_for_session(session_id)
    index = LocalVectorIndex()
    for index_number, message in enumerate(memory.get_context(), start=1):
        index.add(
            f"{session_id}:{index_number}",
            message.get("content", ""),
        )
    return {"matches": [match.to_dict() for match in index.search(query, limit=limit)]}


@app.get("/approvals")
def list_approvals(status: Optional[str] = Query(None)):
    return {"approvals": approval_store.list(status=status)}


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
    agent = _build_agent(config.AGENT_MODE, "default")
    trace = TraceLog()
    result = agent.execute_approved(
        decided["action"], decided["parameters"], trace=trace
    )
    return {"approval": decided, "result": result, "trace": trace.summary()}


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
    if db_module.db_available and db_module.db_manager is not None:
        return check_health(db_module.db_manager, redis_manager, config.APP_NAME)
    # Offline mode: report degraded but alive so the service is still usable.
    return {
        "status": "degraded",
        "service": config.APP_NAME,
        "dependencies": {"database": "offline", "redis": "offline"},
    }
