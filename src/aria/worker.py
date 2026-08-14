"""Celery worker with real agent domain tasks.

Built via ``aria.internal.vendor_core.tasks.create_celery_app`` and importable without a
running broker (the broker URL is only contacted when a worker starts or a task
is dispatched). Tasks run real agent work against the active stores (DB-backed
when available, in-memory otherwise), mirroring the synchronous API so a run can
be dispatched asynchronously and approval timeouts can be swept on a schedule.
"""

import json
import time
from typing import Any, Dict, Optional

from aria.internal.vendor_core.tasks import create_celery_app

from .config import AppConfig
from .internal.core.rate_limit import FixedWindowRateLimiter
from .internal.core.retry import RetryPolicy
from .internal.core.sweeper import ApprovalSweeper

config = AppConfig()
celery_app = create_celery_app(
    config.APP_NAME,
    broker_url=config.CELERY_BROKER_URL,
    backend_url=config.CELERY_RESULT_BACKEND,
)


def _build_agent(mode: str, session_id: str):
    """Construct an agent bound to the active stores (DB or in-memory)."""
    from . import db as db_module
    from .agents import AriaAgent
    from .approvals import ApprovalGate
    from .llm_client import AgentLLMClient
    from .memory import get_memory
    from .routing import build_router
    from .tools import build_default_registry

    try:
        retry_config = json.loads(config.ARIA_TOOL_RETRY_POLICIES or "{}")
    except (TypeError, json.JSONDecodeError):
        retry_config = {}
    retry_policies = {}
    for tool, value in retry_config.items():
        if isinstance(value, dict):
            try:
                retry_policies[tool] = RetryPolicy(
                    max_attempts=int(value.get("max_attempts", 1)),
                    backoff_seconds=float(value.get("backoff_seconds", 0.0)),
                )
            except (TypeError, ValueError):
                continue

    db_module.check_db()
    task_store = db_module.build_task_store()
    approval_store = db_module.build_approval_store(
        timeout=config.APPROVAL_TIMEOUT_SECONDS
    )
    registry = build_default_registry(task_store=task_store)
    router = build_router(config.AGENT_ROUTING, llm_client=AgentLLMClient())
    gate = ApprovalGate(enabled=True, mode=mode, store=approval_store)
    agent = AriaAgent(
        registry,
        gate,
        max_steps=config.AGENT_MAX_STEPS,
        router=router,
        memory=get_memory(session_id),
        mode=mode,
        planning_mode=config.ARIA_PLANNING_MODE,
        safety_mode=config.ARIA_SAFETY_MODE,
        retry_policies=retry_policies,
        rate_limiter=(
            FixedWindowRateLimiter(
                limit=config.ARIA_RATE_LIMIT_PER_TOOL,
                window_seconds=config.ARIA_RATE_LIMIT_WINDOW_SECONDS,
                clock=time.time,
            )
            if config.ARIA_RATE_LIMIT_PER_TOOL > 0
            else None
        ),
        session_id=session_id,
    )
    return agent, db_module.build_run_store(), approval_store


def _run_agent(query: str, session_id: str, mode: str) -> Dict[str, Any]:
    """Pure helper: run the agent once and persist the run."""
    agent, run_store, _ = _build_agent(mode, session_id)
    result = agent.run_structured(query)
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
    return result.to_dict()


@celery_app.task(name="aria.run_agent")
def run_agent_task(
    query: str, session_id: str = "default", mode: Optional[str] = None
) -> Dict[str, Any]:
    """Async task: run the agent and persist the resulting run."""
    return _run_agent(query, session_id, mode or config.AGENT_MODE)


def _sweep_expired_approvals(approval_store) -> Dict[str, Any]:
    """Pure helper: count approvals that have timed out into ``expired``."""
    result = ApprovalSweeper(approval_store).sweep()
    return {"total": result["checked"], "expired": result["expired"]}


@celery_app.task(name="aria.sweep_expired_approvals")
def sweep_expired_approvals_task() -> Dict[str, Any]:
    """Async task: materialise approval timeouts (pending -> expired)."""
    _, _, approval_store = _build_agent(config.AGENT_MODE, "default")
    return _sweep_expired_approvals(approval_store)
