"""FastAPI gateway for the Hermes agent framework.

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

import time
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from shared_core.errors import BaseApplicationError, application_error_handler
from shared_core.health import check_health
from shared_core.logging import setup_logging

from . import db as db_module
from .agents import HermesAgent
from .approvals import ApprovalGate
from .config import AppConfig
from .costs import CostTracker
from .llm_client import AgentLLMClient
from .memory import get_memory
from .routing import build_router
from .store import ApprovalStatus
from .tools import build_default_registry
from .tracing import TraceLog

config = AppConfig()
setup_logging(level=config.LOG_LEVEL, service_name=config.APP_NAME)

app = FastAPI(title=config.APP_NAME, version="1.0.0")
app.add_exception_handler(BaseApplicationError, application_error_handler)

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


def _build_agent(mode: str, session_id: str) -> HermesAgent:
    """Construct a per-request agent bound to the active stores."""
    request_gate = ApprovalGate(enabled=True, mode=mode, store=approval_store)
    return HermesAgent(
        registry,
        request_gate,
        max_steps=config.AGENT_MAX_STEPS,
        router=router,
        memory=get_memory(session_id),
        mode=mode,
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


@app.get("/approvals")
def list_approvals(status: Optional[str] = Query(None)):
    return {"approvals": approval_store.list(status=status)}


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
