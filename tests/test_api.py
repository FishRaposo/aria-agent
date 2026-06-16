"""API tests — every endpoint, success + error paths.

Forces the offline in-memory store path by pointing the DB probe at an
unreachable URL with a 1s timeout, so the suite needs no Postgres. The app is
imported once and shared via a module-scoped TestClient.
"""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    import hermes.config as config_mod

    # Make the startup DB probe fail fast -> in-memory stores.
    original = config_mod.AppConfig

    class FastProbeConfig(original):
        DATABASE_URL: str = "postgresql+psycopg://u:p@127.0.0.1:1/none"
        DB_PROBE_TIMEOUT: int = 1
        AGENT_MODE: str = "free_running"

    config_mod.AppConfig = FastProbeConfig
    try:
        import hermes.db as db_mod
        import hermes.main as main_mod

        importlib.reload(db_mod)
        importlib.reload(main_mod)
        with TestClient(main_mod.app) as test_client:
            yield test_client
    finally:
        config_mod.AppConfig = original


# --------------------------------------------------------------------------- #
# Health + tools
# --------------------------------------------------------------------------- #
def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "hermes-agent-framework"
    assert "dependencies" in data


def test_list_tools(client):
    resp = client.get("/tools")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 5
    assert all("permission" in t for t in tools)


def test_tool_schema(client):
    resp = client.get("/tools/calculator")
    assert resp.status_code == 200
    body = resp.json()
    assert body["permission"] == "safe"
    assert "properties" in body["schema"]


def test_tool_schema_404(client):
    assert client.get("/tools/ghost").status_code == 404


# --------------------------------------------------------------------------- #
# Chat + runs
# --------------------------------------------------------------------------- #
def test_chat_calculator(client):
    resp = client.post("/agent/chat", json={"message": "calculate 120 + 350"})
    assert resp.status_code == 200
    data = resp.json()
    assert "470" in data["reply"]
    assert data["status"] == "completed"
    assert "trace" in data and "cost" in data
    assert data["trace"]["spans"]


def test_chat_persists_run(client):
    resp = client.post("/agent/chat", json={"message": "calculate 1 + 1"})
    run_id = resp.json()["run_id"]
    got = client.get(f"/agent/runs/{run_id}")
    assert got.status_code == 200
    assert got.json()["query"] == "calculate 1 + 1"


def test_list_runs(client):
    client.post("/agent/chat", json={"message": "search for python"})
    resp = client.get("/agent/runs")
    assert resp.status_code == 200
    assert len(resp.json()["runs"]) >= 1


def test_run_not_found(client):
    assert client.get("/agent/runs/nope").status_code == 404


def test_trace_endpoint(client):
    run_id = client.post("/agent/chat", json={"message": "calculate 2 + 3"}).json()[
        "run_id"
    ]
    resp = client.get(f"/agent/trace/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["trace"]["trace_id"]


def test_trace_not_found(client):
    assert client.get("/agent/trace/nope").status_code == 404


# --------------------------------------------------------------------------- #
# Approvals
# --------------------------------------------------------------------------- #
def test_approval_gated_chat_creates_pending(client):
    resp = client.post(
        "/agent/chat",
        json={"message": "create a task to ship it", "mode": "approval_gated"},
    )
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert data["approval"]["status"] == "pending"


def test_list_approvals(client):
    client.post(
        "/agent/chat",
        json={"message": "create a task to review", "mode": "approval_gated"},
    )
    resp = client.get("/approvals")
    assert resp.status_code == 200
    assert len(resp.json()["approvals"]) >= 1


def test_list_approvals_filtered(client):
    resp = client.get("/approvals", params={"status": "pending"})
    assert resp.status_code == 200
    assert all(a["status"] == "pending" for a in resp.json()["approvals"])


def test_approve_executes_tool(client):
    pending = client.post(
        "/agent/chat",
        json={"message": "create a task to file taxes", "mode": "approval_gated"},
    ).json()
    approval_id = pending["approval"]["id"]
    resp = client.post(f"/approvals/{approval_id}/approve", json={"reason": "ok"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["approval"]["status"] == "approved"
    assert "Task created" in body["result"]
    assert body["trace"]["trace_id"]


def test_reject(client):
    pending = client.post(
        "/agent/chat",
        json={"message": "draft an email to a@b.com", "mode": "approval_gated"},
    ).json()
    approval_id = pending["approval"]["id"]
    resp = client.post(f"/approvals/{approval_id}/reject", json={"reason": "no"})
    assert resp.status_code == 200
    assert resp.json()["approval"]["status"] == "rejected"


def test_approve_unknown_404(client):
    assert client.post("/approvals/ghost/approve").status_code == 404


def test_reject_unknown_404(client):
    assert client.post("/approvals/ghost/reject").status_code == 404


def test_double_approve_conflicts(client):
    pending = client.post(
        "/agent/chat",
        json={"message": "create a task to deploy", "mode": "approval_gated"},
    ).json()
    approval_id = pending["approval"]["id"]
    client.post(f"/approvals/{approval_id}/approve")
    second = client.post(f"/approvals/{approval_id}/approve")
    assert second.status_code == 409


def test_get_single_approval(client):
    pending = client.post(
        "/agent/chat",
        json={"message": "create a task to audit", "mode": "approval_gated"},
    ).json()
    approval_id = pending["approval"]["id"]
    resp = client.get(f"/approvals/{approval_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == approval_id


def test_get_approval_404(client):
    assert client.get("/approvals/ghost").status_code == 404


def test_approve_expired_between_check_and_decide_does_not_execute(client, monkeypatch):
    """If the approval expires between the PENDING check and decide(), the
    endpoint must NOT execute the gated tool — only return the decided record.
    """
    import hermes.main as main_mod
    from hermes.store import ApprovalStatus

    pending = client.post(
        "/agent/chat",
        json={"message": "create a task to expire", "mode": "approval_gated"},
    ).json()
    approval_id = pending["approval"]["id"]

    # Simulate a race: the status check passes (still pending), but by the time
    # decide() runs the approval has expired, so it returns an EXPIRED record.
    real_decide = main_mod.approval_store.decide

    def expiring_decide(aid, approved, reason=None):
        real_decide(aid, approved=approved, reason=reason)
        rec = main_mod.approval_store.get(aid)
        rec = dict(rec)
        rec["status"] = ApprovalStatus.EXPIRED.value
        return rec

    monkeypatch.setattr(main_mod.approval_store, "decide", expiring_decide)

    # execute_approved must never be reached for a non-approved decision.
    def fail_execute(*args, **kwargs):  # pragma: no cover - asserts non-invocation
        raise AssertionError("execute_approved called for a non-approved action")

    monkeypatch.setattr(main_mod.HermesAgent, "execute_approved", fail_execute)

    resp = client.post(f"/approvals/{approval_id}/approve")
    assert resp.status_code == 200
    body = resp.json()
    assert body["approval"]["status"] == ApprovalStatus.EXPIRED.value
    assert "result" not in body
    assert "trace" not in body
