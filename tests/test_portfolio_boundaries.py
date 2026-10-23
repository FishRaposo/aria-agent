"""Execution-boundary regressions using real HTTP and durable SQLite stores."""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from shutil import rmtree
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

import aria.models  # noqa: F401 - register tables before creating the test database
from aria.agents import AriaAgent
from aria.approvals import ApprovalGate
from aria.internal.vendor_core.database import DatabaseManager
from aria.routing import RouteDecision
from aria.store import InMemoryApprovalStore
from aria.store_db import DatabaseApprovalStore
from aria.tools import Permission, ToolRegistry
from aria.tracing import TraceLog


class ActionInput(BaseModel):
    value: str


def counting_registry(effects):
    registry = ToolRegistry()
    registry.add(
        "write",
        ActionInput,
        lambda value: effects.append(value) or "written",
        Permission.REQUIRES_APPROVAL,
    )
    return registry


def strict_agent(store, registry, *, arguments=None, gate_enabled=True):
    class Router:
        def route(self, query, context=None, cost_tracker=None):
            return RouteDecision(tool="write", arguments=arguments or {"value": query})

    return AriaAgent(
        registry,
        ApprovalGate(mode="approval_gated", store=store, enabled=gate_enabled),
        mode="approval_gated",
        safety_mode="block",
        router=Router(),
    )


@pytest.fixture(params=["memory", "sqlite"])
def boundary_store(request, backend_directory):
    if request.param == "memory":
        yield InMemoryApprovalStore()
        return
    manager = DatabaseManager(
        f"sqlite:///{(backend_directory / 'approvals.db').as_posix()}"
    )
    manager.create_tables()
    try:
        yield DatabaseApprovalStore(manager.get_session)
    finally:
        manager.engine.dispose()


@pytest.fixture
def backend_directory():
    # Windows sandbox identities cannot access Python-created mode0700 pytest
    # directories. Use a private unique directory with inherited workspace ACL.
    directory = Path(".tmp") / f"backend-{uuid4().hex}"
    directory.mkdir(parents=True)
    try:
        yield directory
    finally:
        rmtree(directory)


def test_approval_parameters_are_detached_from_input_and_response(boundary_store):
    # Mutating either caller-owned dict must never change what was reviewed.
    arguments = {"nested": {"value": "reviewed"}}
    approval = boundary_store.create("write", arguments, run_id="run")
    arguments["nested"]["value"] = "changed input"
    approval["parameters"]["nested"]["value"] = "changed response"
    assert boundary_store.get(approval["id"])["parameters"] == {
        "nested": {"value": "reviewed"}
    }


def test_strict_direct_execution_requires_a_bound_approval(boundary_store):
    # Calling the public out-of-band seam must not manufacture authorization.
    effects = []
    agent = strict_agent(boundary_store, counting_registry(effects))
    try:
        agent.execute_approved("write", {"value": "unreviewed"})
    except PermissionError:
        pass
    assert effects == []


def test_strict_invalid_schema_is_denied_before_review(boundary_store):
    effects = []
    agent = strict_agent(
        boundary_store, counting_registry(effects), arguments={"bad": 1}
    )
    result = agent.run_structured("write")
    assert result.status == "blocked"
    assert result.approval is None
    assert effects == []
    assert boundary_store.list() == []


def test_strict_disabled_gate_cannot_bypass_review(boundary_store):
    effects = []
    agent = strict_agent(boundary_store, counting_registry(effects), gate_enabled=False)
    result = agent.run_structured("write")
    assert result.status == "blocked"
    assert effects == []


@pytest.fixture
def strict_http(boundary_store, monkeypatch):
    import aria.main as main

    effects = []
    monkeypatch.setattr(main, "approval_store", boundary_store)
    monkeypatch.setattr(main, "registry", counting_registry(effects))
    monkeypatch.setattr(main.config, "AGENT_MODE", "approval_gated")
    monkeypatch.setattr(main.config, "ARIA_SAFETY_MODE", "block")
    monkeypatch.setattr(main.db_module, "db_available", False)
    with TestClient(main.app) as client:
        yield client, effects


def test_concurrent_http_approve_executes_only_once(
    boundary_store, strict_http, monkeypatch
):
    # Both HTTP handlers see pending before either decides; decide alone is not
    # execution ownership. This reproduced two real tool invocations previously.
    client, effects = strict_http
    approval = boundary_store.create("write", {"value": "reviewed"}, run_id="run")
    barrier = Barrier(2)
    original_get = boundary_store.get

    def synchronized_get(approval_id):
        record = original_get(approval_id)
        if record and record["status"] == "pending":
            barrier.wait(timeout=10)
        return record

    monkeypatch.setattr(boundary_store, "get", synchronized_get)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(f"/approvals/{approval['id']}/approve"), range(2)
            )
        )
    assert effects == ["reviewed"]
    assert sorted(response.status_code for response in responses) == [200, 409]


@pytest.mark.parametrize("alteration", ["action", "arguments", "run", "missing"])
def test_altered_or_missing_binding_has_zero_effects(boundary_store, alteration):
    effects = []
    registry = counting_registry(effects)
    registry.add(
        "other",
        ActionInput,
        lambda value: effects.append(value),
        Permission.REQUIRES_APPROVAL,
    )
    approval = boundary_store.create("write", {"value": "reviewed"}, run_id="run")
    boundary_store.decide(approval["id"], approved=True)
    trace = TraceLog()
    with pytest.raises(PermissionError):
        strict_agent(boundary_store, registry).execute_approved(
            "other" if alteration == "action" else "write",
            {"value": "altered" if alteration == "arguments" else "reviewed"},
            approval_id="missing" if alteration == "missing" else approval["id"],
            run_id="other-run" if alteration == "run" else "run",
            trace=trace,
        )
    assert effects == []
    assert trace.entries[-1]["name"] == "execution_denied"
    assert boundary_store.get(approval["id"])["execution_status"] is None


@pytest.mark.parametrize(
    "state", ["pending", "rejected", "expired", "approved-expired"]
)
def test_unapproved_or_expired_review_has_zero_effects(
    boundary_store, state, monkeypatch
):
    effects = []
    approval = boundary_store.create("write", {"value": "reviewed"}, run_id="run")
    if state in {"rejected", "approved-expired"}:
        boundary_store.decide(approval["id"], approved=state == "approved-expired")
    if "expired" in state:
        monkeypatch.setattr("time.time", lambda: approval["expires_at"] + 1)
    with pytest.raises(PermissionError):
        strict_agent(boundary_store, counting_registry(effects)).execute_approved(
            "write", {"value": "reviewed"}, approval_id=approval["id"], run_id="run"
        )
    assert effects == []


@pytest.mark.parametrize(
    "action,arguments",
    [
        ("unknown", {"value": "reviewed"}),
        ("write", {"wrong": 1}),
    ],
)
def test_http_unknown_tool_or_invalid_schema_has_zero_effects(
    boundary_store, strict_http, action, arguments
):
    client, effects = strict_http
    approval = boundary_store.create(action, arguments, run_id="run")
    response = client.post(f"/approvals/{approval['id']}/approve")
    assert response.status_code == 409
    assert (
        response.json()["detail"]["trace"]["entries"][-1]["name"] == "execution_denied"
    )
    assert effects == []
    assert boundary_store.get(approval["id"])["execution_status"] is None


def test_strict_unknown_tool_denied_before_review(boundary_store):
    effects = []
    registry = counting_registry(effects)
    agent = strict_agent(boundary_store, registry)
    del registry.tools["write"]
    result = agent.run_structured("write")
    assert result.status == "blocked"
    assert result.trace["entries"][-1]["name"] == "execution_denied"
    assert boundary_store.list() == []
    assert effects == []


def test_successful_execution_records_single_use_metadata(boundary_store):
    effects = []
    approval = boundary_store.create("write", {"value": "reviewed"}, run_id="run")
    boundary_store.decide(approval["id"], approved=True)
    agent = strict_agent(boundary_store, counting_registry(effects))
    assert (
        agent.execute_approved(
            "write", {"value": "reviewed"}, approval_id=approval["id"], run_id="run"
        )
        == "written"
    )
    with pytest.raises(PermissionError):
        agent.execute_approved(
            "write", {"value": "reviewed"}, approval_id=approval["id"], run_id="run"
        )
    record = boundary_store.get(approval["id"])
    assert record["status"] == "approved"
    assert record["execution_status"] == "completed"
    assert record["execution_claimed_at"] <= record["execution_completed_at"]
    assert "execution_token" not in record
    assert effects == ["reviewed"]


def test_legacy_public_execution_and_defaults_remain_available(boundary_store):
    effects = []
    registry = counting_registry(effects)
    agent = AriaAgent(registry, ApprovalGate())
    assert agent.mode == "free_running"
    assert agent.engine.safety.policy == "warn"
    assert agent.execute_approved("write", {"value": "legacy"}) == "written"
    assert effects == ["legacy"]


def test_legacy_bound_execution_preserves_schema_coercion(boundary_store):
    # Single-use ownership must not silently enable strict schemas globally.
    class NumberInput(BaseModel):
        value: int

    effects = []
    registry = ToolRegistry()
    registry.add("number", NumberInput, lambda value: effects.append(value) or value)
    approval = boundary_store.create("number", {"value": "3"}, run_id="run")
    boundary_store.decide(approval["id"], approved=True)
    agent = AriaAgent(registry, ApprovalGate(store=boundary_store))
    assert (
        agent.execute_approved(
            "number", {"value": "3"}, approval_id=approval["id"], run_id="run"
        )
        == "3"
    )
    assert effects == [3]


def test_claimed_execution_never_retries_even_if_permission_changes(boundary_store):
    from aria.internal.core.retry import RetryPolicy

    effects = []

    def uncertain(value):
        effects.append(value)
        raise RuntimeError("effect happened before failure")

    registry = ToolRegistry()
    registry.add("write", ActionInput, uncertain, Permission.SAFE)
    approval = boundary_store.create("write", {"value": "once"}, run_id="run")
    boundary_store.decide(approval["id"], approved=True)
    agent = strict_agent(boundary_store, registry)
    agent.engine.retry_policies["write"] = RetryPolicy(max_attempts=3)
    agent.execute_approved(
        "write", {"value": "once"}, approval_id=approval["id"], run_id="run"
    )
    assert effects == ["once"]
    assert boundary_store.get(approval["id"])["execution_status"] == "failed"


@pytest.mark.parametrize("outcome", ["completed", "failed", "crash"])
def test_file_sqlite_restart_never_retries_a_consumed_claim(
    backend_directory, monkeypatch, outcome
):
    from aria.internal.core.retry import RetryPolicy

    url = f"sqlite:///{(backend_directory / 'durable.db').as_posix()}"
    manager = DatabaseManager(url)
    manager.create_tables()
    store = DatabaseApprovalStore(manager.get_session)
    marker = backend_directory / "effects.txt"

    def write(value):
        with marker.open("a", encoding="utf-8") as stream:
            stream.write(value + "\n")
        if outcome == "crash":
            raise SystemExit("process stopped after effect, before outcome persistence")
        if outcome == "failed":
            raise RuntimeError("uncertain tool failure after effect")
        return "written"

    registry = ToolRegistry()
    registry.add("write", ActionInput, write, Permission.REQUIRES_APPROVAL)
    approval = store.create("write", {"value": "reviewed"}, run_id="run")
    store.decide(approval["id"], approved=True)
    agent = strict_agent(store, registry)
    agent.engine.retry_policies["write"] = RetryPolicy(max_attempts=3)
    try:
        if outcome == "crash":
            with pytest.raises(SystemExit):
                agent.execute_approved(
                    "write",
                    {"value": "reviewed"},
                    approval_id=approval["id"],
                    run_id="run",
                )
        else:
            agent.execute_approved(
                "write", {"value": "reviewed"}, approval_id=approval["id"], run_id="run"
            )
    finally:
        manager.engine.dispose()

    # New engine and store simulate a service restart over the same real file.
    restarted = DatabaseManager(url)
    store = DatabaseApprovalStore(restarted.get_session)
    try:
        record = store.get(approval["id"])
        assert record["execution_status"] == (
            "claimed" if outcome == "crash" else outcome
        )
        assert (record["execution_completed_at"] is None) == (outcome == "crash")
        import aria.main as main

        monkeypatch.setattr(main, "approval_store", store)
        monkeypatch.setattr(main, "registry", registry)
        monkeypatch.setattr(main.config, "AGENT_MODE", "approval_gated")
        monkeypatch.setattr(main.config, "ARIA_SAFETY_MODE", "block")
        with TestClient(main.app) as client:
            assert (
                client.post(f"/approvals/{approval['id']}/approve").status_code == 409
            )
        with pytest.raises(PermissionError):
            strict_agent(store, registry).execute_approved(
                "write", {"value": "reviewed"}, approval_id=approval["id"], run_id="run"
            )
        assert marker.read_text(encoding="utf-8") == "reviewed\n"
    finally:
        restarted.engine.dispose()


def test_additive_migration_preserves_old_review_but_does_not_grant_execution(
    backend_directory, monkeypatch
):
    import time
    from datetime import datetime, timezone

    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command

    url = f"sqlite:///{(backend_directory / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0001_initial")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO approvals (id, run_id, action, parameters_json, status, expires_at, created_at, updated_at) "
                "VALUES (:id, :run, :action, :params, :status, :expiry, :created, :created)"
            ),
            {
                "id": "old-review",
                "run": "run",
                "action": "write",
                "params": '{"value":"reviewed"}',
                "status": "pending",
                "expiry": time.time() + 300,
                "created": datetime.now(timezone.utc).isoformat(),
            },
        )
    engine.dispose()
    command.upgrade(config, "head")
    manager = DatabaseManager(url)
    try:
        store = DatabaseApprovalStore(manager.get_session)
        assert store.get("old-review")["parameters"] == {"value": "reviewed"}
        store.decide("old-review", approved=True)
        effects = []
        agent = strict_agent(store, counting_registry(effects))
        with pytest.raises(PermissionError):
            agent.execute_approved(
                "write", {"value": "reviewed"}, approval_id="old-review", run_id="run"
            )
        assert effects == []
        fresh = store.create("write", {"value": "fresh review"}, run_id="new-run")
        store.decide(fresh["id"], approved=True)
        agent.execute_approved(
            "write",
            {"value": "fresh review"},
            approval_id=fresh["id"],
            run_id="new-run",
        )
        assert effects == ["fresh review"]
    finally:
        manager.engine.dispose()


@pytest.mark.parametrize("escape", ["traversal", "symlink"])
def test_file_tool_workspace_escape_never_reads_outside(
    backend_directory, monkeypatch, escape
):
    from aria.builtin_tools.file_reader import file_reader

    sandbox = backend_directory / "sandbox"
    sandbox.mkdir()
    outside = backend_directory / "outside.txt"
    outside.write_text("private fixture", encoding="utf-8")
    monkeypatch.setenv("ARIA_SANDBOX_DIR", str(sandbox.resolve()))
    filepath = "../outside.txt"
    if escape == "symlink":
        outside_directory = backend_directory / "outside-directory"
        outside_directory.mkdir()
        outside = outside_directory / "outside.txt"
        outside.write_text("private fixture", encoding="utf-8")
        link = sandbox / "escape"
        try:
            link.symlink_to(outside_directory.resolve(), target_is_directory=True)
        except OSError as exc:
            if os.name != "nt":
                raise
            # A directory junction is the Windows reparse-point equivalent and
            # needs no developer-mode privilege. Its target is our own fixture.
            created = subprocess.run(
                [
                    "cmd",
                    "/c",
                    "mklink",
                    "/J",
                    str(link.resolve()),
                    str(outside_directory.resolve()),
                ],
                capture_output=True,
                text=True,
            )
            assert created.returncode == 0, (
                f"Symlink/junction unavailable: {exc}; {created.stderr}"
            )
        filepath = "escape/outside.txt"
    reads = []
    read_text = Path.read_text

    def tracked_read(path, *args, **kwargs):
        if path.resolve() == outside.resolve():
            reads.append(path)
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", tracked_read)
    result = file_reader(filepath)
    assert "access denied" in result
    assert "private fixture" not in result
    assert reads == []


@pytest.mark.parametrize("route", ["/agent/chat", "/agent/chat/stream"])
def test_strict_http_cannot_downgrade_execution_mode(strict_http, route):
    client, effects = strict_http
    response = client.post(route, json={"message": "write", "mode": "free_running"})
    assert response.status_code == 409
    assert effects == []


def test_execution_uses_immutable_claimed_arguments(boundary_store, monkeypatch):
    # A caller changing its own dict after the claim must not change the action.
    effects = []
    arguments = {"value": "reviewed"}
    approval = boundary_store.create("write", arguments, run_id="run")
    boundary_store.decide(approval["id"], approved=True)
    claim = boundary_store.claim_execution

    def mutate_after_claim(*args, **kwargs):
        token = claim(*args, **kwargs)
        arguments["value"] = "altered after claim"
        return token

    monkeypatch.setattr(boundary_store, "claim_execution", mutate_after_claim)
    strict_agent(boundary_store, counting_registry(effects)).execute_approved(
        "write", arguments, approval_id=approval["id"], run_id="run"
    )
    assert effects == ["reviewed"]


def test_http_conflicting_stale_reject_reports_conflict(
    boundary_store, strict_http, monkeypatch
):
    # Reject must not report success if another worker already approved it.
    client, effects = strict_http
    approval = boundary_store.create("write", {"value": "reviewed"}, run_id="run")
    barrier, approved = Barrier(2), Event()
    get, decide = boundary_store.get, boundary_store.decide

    def synchronized_get(approval_id):
        record = get(approval_id)
        if record and record["status"] == "pending":
            barrier.wait(timeout=10)
        return record

    def ordered_decide(approval_id, approved: bool, reason=None):
        if not approved:
            assert approval_done.wait(timeout=10)
        result = decide(approval_id, approved=approved, reason=reason)
        if approved:
            approval_done.set()
        return result

    approval_done = approved
    monkeypatch.setattr(boundary_store, "get", synchronized_get)
    monkeypatch.setattr(boundary_store, "decide", ordered_decide)
    with ThreadPoolExecutor(max_workers=2) as pool:
        approve = pool.submit(client.post, f"/approvals/{approval['id']}/approve")
        reject = pool.submit(client.post, f"/approvals/{approval['id']}/reject")
        assert approve.result().status_code == 200
        assert reject.result().status_code == 409
    assert effects == ["reviewed"]
