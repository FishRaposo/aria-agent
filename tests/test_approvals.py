"""Approval queue tests — pending / approve / reject / timeout.

Runs the same lifecycle assertions against both the in-memory store and the
DB-backed store (over an in-memory SQLite MockDatabase) so behaviour matches.
"""

import time

import pytest

from hermes.approvals import ApprovalGate
from hermes.store import ApprovalStatus, InMemoryApprovalStore
from hermes.store_db import DatabaseApprovalStore


@pytest.fixture(params=["memory", "db"])
def store(request, mock_db):
    if request.param == "memory":
        return InMemoryApprovalStore()
    return DatabaseApprovalStore(mock_db.get_session)


class TestApprovalLifecycle:
    def test_create_is_pending(self, store):
        rec = store.create("task_creator", {"title": "x"})
        assert rec["status"] == ApprovalStatus.PENDING.value
        assert rec["seconds_remaining"] > 0

    def test_approve(self, store):
        rec = store.create("task_creator", {"title": "x"})
        decided = store.decide(rec["id"], approved=True, reason="ok")
        assert decided["status"] == ApprovalStatus.APPROVED.value
        assert decided["reason"] == "ok"
        assert decided["decided_at"] is not None

    def test_reject(self, store):
        rec = store.create("email_draft", {"to": "a@b.com"})
        decided = store.decide(rec["id"], approved=False, reason="no")
        assert decided["status"] == ApprovalStatus.REJECTED.value
        assert decided["reason"] == "no"

    def test_get_unknown_returns_none(self, store):
        assert store.get("does-not-exist") is None

    def test_decide_unknown_returns_none(self, store):
        assert store.decide("does-not-exist", approved=True) is None

    def test_list_filters_by_status(self, store):
        a = store.create("task_creator", {"t": 1})
        store.create("task_creator", {"t": 2})
        store.decide(a["id"], approved=True)
        pending = store.list(status="pending")
        approved = store.list(status="approved")
        assert len(pending) == 1
        assert len(approved) == 1

    def test_timeout_expires_pending(self, store):
        rec = store.create("task_creator", {"t": 1}, timeout=0.0)
        time.sleep(0.01)
        fetched = store.get(rec["id"])
        assert fetched["status"] == ApprovalStatus.EXPIRED.value

    def test_cannot_approve_expired(self, store):
        rec = store.create("task_creator", {"t": 1}, timeout=0.0)
        time.sleep(0.01)
        decided = store.decide(rec["id"], approved=True)
        assert decided["status"] == ApprovalStatus.EXPIRED.value

    def test_double_decide_keeps_first(self, store):
        rec = store.create("task_creator", {"t": 1})
        store.decide(rec["id"], approved=True)
        again = store.decide(rec["id"], approved=False)
        assert again["status"] == ApprovalStatus.APPROVED.value


class TestApprovalGate:
    def test_free_running_auto_approves(self):
        gate = ApprovalGate(enabled=True, mode="free_running")
        out = gate.evaluate("task_creator", {}, requires_approval=True)
        assert out["decision"] == "approved"
        assert out["approval"] is None

    def test_gated_creates_pending_for_risky(self):
        store = InMemoryApprovalStore()
        gate = ApprovalGate(enabled=True, mode="approval_gated", store=store)
        out = gate.evaluate("task_creator", {"t": 1}, requires_approval=True)
        assert out["decision"] == "pending"
        assert out["approval"]["status"] == "pending"

    def test_gated_passes_safe_tool(self):
        store = InMemoryApprovalStore()
        gate = ApprovalGate(enabled=True, mode="approval_gated", store=store)
        out = gate.evaluate("calculator", {}, requires_approval=False)
        assert out["decision"] == "approved"

    def test_disabled_gate_approves_everything(self):
        gate = ApprovalGate(enabled=False, mode="approval_gated")
        out = gate.evaluate("task_creator", {}, requires_approval=True)
        assert out["decision"] == "approved"

    def test_legacy_boolean_api(self):
        assert ApprovalGate(enabled=False).request_approval("x", {}) is True
        assert (
            ApprovalGate(enabled=True, mode="free_running").request_approval("x", {})
            is True
        )
        assert (
            ApprovalGate(enabled=True, mode="approval_gated").request_approval("x", {})
            is False
        )
