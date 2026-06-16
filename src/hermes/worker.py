"""Celery worker with real agent domain tasks.

Built via ``shared_core.tasks.create_celery_app`` and importable without a
running broker (the broker URL is only contacted when a worker starts or a task
is dispatched). Tasks run real agent work against the active stores (DB-backed
when available, in-memory otherwise), mirroring the synchronous API so a run can
be dispatched asynchronously and approval timeouts can be swept on a schedule.
"""

import time
from typing import Any, Dict, Optional

from shared_core.tasks import create_celery_app

from .config import AppConfig

config = AppConfig()
celery_app = create_celery_app(
    config.APP_NAME,
    broker_url=config.CELERY_BROKER_URL,
    backend_url=config.CELERY_RESULT_BACKEND,
)


def _build_agent(mode: str, session_id: str):
    """Construct an agent bound to the active stores (DB or in-memory)."""
    from . import db as db_module
    from .agents import HermesAgent
    from .approvals import ApprovalGate
    from .llm_client import AgentLLMClient
    from .memory import get_memory
    from .routing import build_router
    from .tools import build_default_registry

    db_module.check_db()
    task_store = db_module.build_task_store()
    approval_store = db_module.build_approval_store(
        timeout=config.APPROVAL_TIMEOUT_SECONDS
    )
    registry = build_default_registry(task_store=task_store)
    router = build_router(config.AGENT_ROUTING, llm_client=AgentLLMClient())
    gate = ApprovalGate(enabled=True, mode=mode, store=approval_store)
    agent = HermesAgent(
        registry,
        gate,
        max_steps=config.AGENT_MAX_STEPS,
        router=router,
        memory=get_memory(session_id),
        mode=mode,
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


@celery_app.task(name="hermes.run_agent")
def run_agent_task(
    query: str, session_id: str = "default", mode: Optional[str] = None
) -> Dict[str, Any]:
    """Async task: run the agent and persist the resulting run."""
    return _run_agent(query, session_id, mode or config.AGENT_MODE)


def _sweep_expired_approvals(approval_store) -> Dict[str, Any]:
    """Pure helper: count approvals that have timed out into ``expired``."""
    approvals = approval_store.list()
    expired = [a for a in approvals if a["status"] == "expired"]
    return {"total": len(approvals), "expired": len(expired)}


@celery_app.task(name="hermes.sweep_expired_approvals")
def sweep_expired_approvals_task() -> Dict[str, Any]:
    """Async task: materialise approval timeouts (pending -> expired)."""
    _, _, approval_store = _build_agent(config.AGENT_MODE, "default")
    return _sweep_expired_approvals(approval_store)
