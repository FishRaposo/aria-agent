"""Celery worker tests — importable without a broker, real tasks."""

from unittest.mock import patch

from aria import worker
from aria.approvals import ApprovalGate
from aria.store import InMemoryApprovalStore


def test_celery_app_importable_without_broker():
    assert worker.celery_app is not None
    assert "aria.run_agent" in worker.celery_app.tasks
    assert "aria.sweep_expired_approvals" in worker.celery_app.tasks


def test_run_agent_helper_offline():
    out = worker._run_agent("calculate 2 + 2", "sess", "free_running")
    assert out["status"] == "completed"
    assert "4" in out["response"]
    assert "trace" in out and "cost" in out


def test_run_agent_task_runs_eagerly():
    out = worker.run_agent_task.run("calculate 10 + 5", "s", "free_running")
    assert "15" in out["response"]


def test_sweep_expired_helper():
    store = InMemoryApprovalStore()
    store.create("task_creator", {"t": 1}, timeout=0.0)
    import time

    time.sleep(0.01)
    result = worker._sweep_expired_approvals(store)
    assert result["total"] == 1
    assert result["expired"] == 1


def test_sweep_task_runs_eagerly():
    store = InMemoryApprovalStore()
    agent_stub = (None, None, store)
    with patch.object(worker, "_build_agent", return_value=agent_stub):
        out = worker.sweep_expired_approvals_task.run()
    assert "total" in out and "expired" in out


def test_gate_uses_provided_store():
    store = InMemoryApprovalStore()
    gate = ApprovalGate(enabled=True, mode="approval_gated", store=store)
    gate.evaluate("task_creator", {"t": 1}, requires_approval=True)
    assert len(store.list(status="pending")) == 1
