"""Connected API contracts backed by real HTTP and memory or durable SQLite."""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from aria.internal.vendor_core.database import DatabaseManager
from aria.memory import AgentMemory, PersistentMemory
from aria.store import InMemoryApprovalStore, InMemoryRunStore, InMemoryTaskStore
from aria.store_db import DatabaseApprovalStore, DatabaseRunStore, DatabaseTaskStore
from aria.tools import build_default_registry


@pytest.fixture(params=["memory", "sqlite"])
def connected(request, monkeypatch, tmp_path):
    import aria.main as main

    manager = None
    if request.param == "sqlite":
        manager = DatabaseManager(f"sqlite:///{(tmp_path / 'connected.db').as_posix()}")
        manager.create_tables()
        stores = (
            DatabaseRunStore(manager.get_session),
            DatabaseTaskStore(manager.get_session),
            DatabaseApprovalStore(manager.get_session),
        )
    else:
        stores = (InMemoryRunStore(), InMemoryTaskStore(), InMemoryApprovalStore())
    monkeypatch.setattr(main, "run_store", stores[0])
    monkeypatch.setattr(main, "task_store", stores[1])
    monkeypatch.setattr(main, "approval_store", stores[2])
    monkeypatch.setattr(main, "registry", build_default_registry(task_store=stores[1]))
    monkeypatch.setattr(main, "_offline_memories", {})
    monkeypatch.setattr(main.db_module, "db_available", manager is not None)
    monkeypatch.setattr(main.db_module, "db_manager", manager)
    monkeypatch.setattr(main.config, "AGENT_MODE", "approval_gated")
    monkeypatch.setattr(main.config, "ARIA_SAFETY_MODE", "block")
    monkeypatch.setattr(main.config, "AGENT_ROUTING", "keyword")
    monkeypatch.setattr(main.config, "ARIA_PLANNING_MODE", "single")
    from aria.routing import build_router

    monkeypatch.setattr(main, "router", build_router("keyword"))
    with TestClient(main.app) as client:
        yield client, main, manager
    if manager:
        manager.engine.dispose()


def chat(client, message, session="first"):
    response = client.post(
        "/agent/chat", json={"message": message, "session_id": session}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_skills_metadata_and_saved_run_context(connected):
    client, main, _ = connected
    before = client.get("/skills", params={"session_id": "first"})
    assert before.status_code == 200
    assert len(before.json()["catalog"]) == 5
    assert before.json()["activated"] == []
    result = chat(client, "calculate 2 + 3")
    run = client.get(f"/agent/runs/{result['run_id']}").json()
    assert run["session_id"] == "first"
    assert run["skill_context"] is not None
    snapshot = client.get(
        "/skills", params={"session_id": "first", "run_id": result["run_id"]}
    ).json()
    assert snapshot["run_id"] == result["run_id"]
    assert snapshot["activated"][0]["name"] == "calculator"
    assert snapshot["activated"][0]["selection_method"] == "automatic"
    assert snapshot["context_report"]["context_consumed"] is False
    assert (
        client.get(
            "/skills", params={"session_id": "other", "run_id": result["run_id"]}
        ).status_code
        == 404
    )
    assert client.get("/skills", params={"run_id": "missing"}).status_code == 404
    assert main.run_store.get(result["run_id"])["skill_context"] == run["skill_context"]


def test_session_filter_memory_and_latest_skills(connected):
    client, _, _ = connected
    first = chat(client, "calculate 6 + 1", "first")
    second = chat(client, "calculate 9 + 2", "second")
    runs = client.get("/agent/runs", params={"session_id": "first"}).json()["runs"]
    assert [run["id"] for run in runs] == [first["run_id"]]
    assert len(client.get("/agent/runs").json()["runs"]) == 2
    memory = client.get("/agent/memory", params={"session_id": "first"}).json()
    assert memory["session_id"] == "first"
    assert any(
        message["content"] == "calculate 6 + 1" for message in memory["messages"]
    )
    assert all(
        "calculate 9" not in message["content"] for message in memory["messages"]
    )
    assert client.get("/agent/memory?limit=0").status_code == 422
    assert client.get("/agent/memory?limit=201").status_code == 422
    assert client.get("/skills?session_id=second").json()["run_id"] == second["run_id"]


def test_stream_persists_context_and_session(connected):
    client, main, _ = connected
    response = client.post(
        "/agent/chat/stream",
        json={"message": "calculate 7 + 3", "session_id": "stream"},
    )
    assert response.status_code == 200
    assert "event: complete" in response.text
    run = main.run_store.list()[0]
    assert run["session_id"] == "stream"
    assert run["skill_context"] is not None
    assert (
        client.get("/skills?session_id=stream").json()["activated"][0]["name"]
        == "calculator"
    )


def test_approval_execution_reconciles_run_trace_and_memory_once(connected):
    client, main, manager = connected
    result = chat(client, "create task prepare interview")
    approval_id = result["approval"]["id"]
    approved = client.post(f"/approvals/{approval_id}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["approval"]["execution_result"] == approved.json()["result"]
    assert approved.json()["approval"]["execution_trace"]["entries"]
    assert len(main.task_store.list()) == 1
    # Rebuilding stores/memory mirrors the application restart boundary.
    if manager:
        main.run_store = DatabaseRunStore(manager.get_session)
        main.approval_store = DatabaseApprovalStore(manager.get_session)
    snapshots = [client.get(f"/agent/runs/{result['run_id']}").json() for _ in range(3)]
    assert all(run["status"] == "completed" for run in snapshots)
    assert all(run["response"] == approved.json()["result"] for run in snapshots)
    assert snapshots[0]["trace"] == snapshots[2]["trace"]
    assert snapshots[0]["approval"]["execution_status"] == "completed"
    assert any(
        entry["type"] == "tool_call" for entry in snapshots[0]["trace"]["entries"]
    )
    messages = client.get("/agent/memory?session_id=first").json()["messages"]
    final = [
        message for message in messages if "Approval outcome" in message["content"]
    ]
    assert len(final) == 1
    assert "completed" in final[0]["content"]
    assert client.post(f"/approvals/{approval_id}/approve").status_code == 409
    assert len(main.task_store.list()) == 1
    assert client.get("/agent/memory?session_id=second").json()["messages"] == []


@pytest.mark.parametrize("outcome", ["rejected", "expired", "claimed", "failed"])
def test_authoritative_approval_outcome_overlay(connected, outcome):
    client, main, _ = connected
    approval = main.approval_store.create(
        "task_creator",
        {"title": "test", "description": "test"},
        run_id="pending",
        timeout=-1 if outcome == "expired" else 300,
    )
    main.run_store.save(
        {
            "id": "pending",
            "session_id": "first",
            "query": "task",
            "response": "Pending approval",
            "status": "pending_approval",
            "mode": "approval_gated",
            "approval_id": approval["id"],
            "trace": {"entries": [], "spans": []},
            "created_at": time.time(),
        }
    )
    if outcome == "rejected":
        main.approval_store.decide(approval["id"], False)
    elif outcome in {"claimed", "failed"}:
        main.approval_store.decide(approval["id"], True)
        token = main.approval_store.claim_execution(
            approval["id"], approval["action"], approval["parameters"], "pending"
        )
        if outcome == "failed":
            main.approval_store.finish_execution(
                approval["id"],
                token,
                success=False,
                result="failed safely",
                trace={
                    "entries": [{"type": "tool_call", "status": "error"}],
                    "spans": [],
                },
            )
    run = client.get("/agent/runs/pending").json()
    assert run["status"] == (
        "pending_approval"
        if outcome == "claimed"
        else "error"
        if outcome == "failed"
        else "blocked"
    )
    assert run["approval"]["status"] == (
        "approved" if outcome in {"claimed", "failed"} else outcome
    )
    if outcome == "claimed":
        assert "unconfirmed" in run["response"].lower()
        assert client.get("/agent/memory?session_id=first").json()["messages"] == []
    else:
        client.get("/agent/runs/pending")
        assert len(client.get("/agent/memory?session_id=first").json()["messages"]) == 1
    assert main.task_store.list() == []


def test_health_runtime_and_legacy_unknown_context(connected):
    client, main, manager = connected
    main.run_store.save(
        {
            "id": "legacy",
            "query": "old",
            "response": "historical",
            "status": "completed",
            "mode": "free_running",
        }
    )
    run = client.get("/agent/runs/legacy").json()
    assert run["session_id"] is None
    assert run["skill_context"] is None
    assert client.get("/skills?session_id=default&run_id=legacy").status_code == 404
    health = client.get("/health").json()
    assert health["runtime"]["allowed_modes"] == ["approval_gated"]
    assert health["runtime"]["routing_mode"] == "keyword"
    assert health["runtime"]["skill_selection_mode"] == "automatic"
    assert health["runtime"]["persistence"] == ("sqlite" if manager else "memory")


@pytest.mark.parametrize("persistent", [False, True])
def test_memory_event_deduplication_across_threads_and_restart(persistent, tmp_path):
    manager = (
        DatabaseManager(f"sqlite:///{(tmp_path / 'memory.db').as_posix()}")
        if persistent
        else None
    )
    if manager:
        manager.create_tables()
    memory = (
        PersistentMemory(manager.get_session, "session")
        if manager
        else AgentMemory("session")
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda _: memory.add_message_once(
                    "system", "completed", "approval:1:completed"
                ),
                range(16),
            )
        )
    if manager:
        memory = PersistentMemory(manager.get_session, "session")
    assert memory.get_context() == [{"role": "system", "content": "completed"}]
    memory.add_message_once("system", "ignored", "approval:1:completed")
    assert len(memory.get_context()) == 1
    if manager:
        manager.engine.dispose()


def test_additive_migration_preserves_legacy_and_restarts(tmp_path):
    from sqlalchemy import text

    database_url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    environment = {**os.environ, "DATABASE_URL": database_url}
    for revision in ("0002_execution_claim", "head"):
        completed = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            env=environment,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        if revision == "0002_execution_claim":
            manager = DatabaseManager(database_url)
            with manager.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO agent_runs (id, query, mode, status, created_at, updated_at) VALUES ('old', 'historical', 'free_running', 'completed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    )
                )
            manager.engine.dispose()
    manager = DatabaseManager(database_url)
    try:
        store = DatabaseRunStore(manager.get_session)
        assert store.get("old")["session_id"] is None
        assert store.get("old")["skill_context"] is None
        context = {"loaded_instruction_bodies": ["recorded instructions"]}
        store.save(
            {
                "id": "new",
                "query": "new",
                "session_id": "saved",
                "skill_context": context,
                "approval_id": "approval",
            }
        )
        assert (
            DatabaseRunStore(manager.get_session).get("new")["skill_context"] == context
        )
        memory = PersistentMemory(manager.get_session, "saved")
        memory.add_message_once("system", "outcome", "fixed-event")
        assert not PersistentMemory(manager.get_session, "saved").add_message_once(
            "system", "duplicate", "fixed-event"
        )
    finally:
        manager.engine.dispose()


def test_http_tool_failure_is_saved_and_reconciled(connected, monkeypatch):
    client, main, _ = connected
    attempts = []

    def failed_tool(**arguments):
        attempts.append(arguments)
        raise RuntimeError("fixture unavailable")

    monkeypatch.setitem(main.registry.tools, "task_creator", failed_tool)
    run = chat(client, "create task failure example")
    approval_id = run["approval"]["id"]
    response = client.post(f"/approvals/{approval_id}/approve")
    assert response.status_code == 200
    approval = response.json()["approval"]
    assert approval["execution_status"] == "failed"
    assert "fixture unavailable" in approval["execution_result"]
    saved = client.get(f"/agent/runs/{run['run_id']}").json()
    assert saved["status"] == "error"
    assert saved["response"] == approval["execution_result"]
    assert saved["trace"]["entries"][-1]["status"] == "error"
    assert client.post(f"/approvals/{approval_id}/approve").status_code == 409
    assert len(attempts) == 1
    assert main.task_store.list() == []


def test_known_session_legacy_context_is_explicitly_unknown(connected):
    client, main, _ = connected
    main.run_store.save(
        {
            "id": "known-legacy",
            "session_id": "first",
            "query": "old",
            "mode": "free_running",
            "status": "completed",
        }
    )
    snapshot = client.get("/skills?session_id=first&run_id=known-legacy").json()
    assert snapshot["context_available"] is False
    assert snapshot["activated"] == []
    assert len(snapshot["catalog"]) == 5
    assert main.run_store.get("known-legacy").get("skill_context") is None


def test_session_approval_filter_is_not_truncated_by_other_sessions(connected):
    client, main, _ = connected
    own = chat(client, "create task selected session", "first")
    # The global default queue limit must not hide an older selected-session row.
    for number in range(105):
        main.approval_store.create(
            "task_creator",
            {"title": str(number), "description": "other"},
            run_id=f"other-{number}",
        )
    approvals = client.get("/approvals?session_id=first").json()["approvals"]
    assert [approval["id"] for approval in approvals] == [own["approval"]["id"]]
    assert client.get("/approvals?session_id=missing").json()["approvals"] == []


def test_chat_reconciles_missing_final_memory_before_next_turn(connected):
    client, main, _ = connected
    run = chat(client, "create task restart memory")
    approval = run["approval"]
    main.approval_store.decide(approval["id"], True)
    token = main.approval_store.claim_execution(
        approval["id"], approval["action"], approval["parameters"], run["run_id"]
    )
    main.approval_store.finish_execution(
        approval["id"],
        token,
        success=True,
        result="recorded completed result",
        trace={"entries": [], "spans": []},
    )
    # No endpoint has reconciled it yet; simulate the presentation update gap.
    assert not any(
        "Approval outcome" in message["content"]
        for message in main._memory_for_session("first").get_context()
    )
    chat(client, "calculate 5 + 2")
    messages = main._memory_for_session("first").get_context()
    final_index = next(
        index
        for index, message in enumerate(messages)
        if "Approval outcome" in message["content"]
    )
    next_query_index = next(
        index
        for index, message in enumerate(messages)
        if message["content"] == "calculate 5 + 2"
    )
    assert final_index < next_query_index
    assert main.task_store.list() == []
