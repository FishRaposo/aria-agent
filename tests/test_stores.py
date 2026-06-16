"""Run/task store tests + DB-availability probe and selection."""

import time

from hermes import db as db_module
from hermes.store import InMemoryRunStore, InMemoryTaskStore
from hermes.store_db import DatabaseRunStore, DatabaseTaskStore


class TestRunStore:
    def test_save_and_get(self):
        store = InMemoryRunStore()
        store.save(
            {"id": "r1", "query": "q", "response": "a", "created_at": time.time()}
        )
        assert store.get("r1")["query"] == "q"

    def test_list_orders_newest_first(self):
        store = InMemoryRunStore()
        store.save({"id": "a", "query": "1", "created_at": 1})
        store.save({"id": "b", "query": "2", "created_at": 2})
        runs = store.list()
        assert runs[0]["id"] == "b"

    def test_get_missing(self):
        assert InMemoryRunStore().get("nope") is None

    def test_db_run_store_roundtrip(self, mock_db):
        store = DatabaseRunStore(mock_db.get_session)
        store.save(
            {
                "id": "x1",
                "query": "hello",
                "response": "hi",
                "mode": "free_running",
                "status": "completed",
                "route": "keyword",
                "trace": {"steps": 1},
                "cost": {"total_cost": 0.0},
            }
        )
        got = store.get("x1")
        assert got["query"] == "hello"
        assert got["trace"] == {"steps": 1}
        assert len(store.list()) == 1


class TestTaskStore:
    def test_create_and_list(self):
        store = InMemoryTaskStore()
        store.create("T1", "D1")
        store.create("T2", "D2")
        assert len(store.list()) == 2

    def test_db_task_store(self, mock_db):
        store = DatabaseTaskStore(mock_db.get_session)
        task = store.create("Persisted", "desc")
        assert store.get(task["id"])["title"] == "Persisted"


class TestDbProbe:
    def test_check_db_falls_back_offline(self, monkeypatch):
        # Point at an unreachable DB and a short probe timeout.
        monkeypatch.setattr(
            db_module.config,
            "DATABASE_URL",
            "postgresql+psycopg://u:p@127.0.0.1:1/none",
        )
        monkeypatch.setattr(db_module.config, "DB_PROBE_TIMEOUT", 1)
        db_module.db_manager = None
        db_module.db_available = False
        assert db_module.check_db() is False
        # Builders return in-memory stores when DB unavailable.
        assert isinstance(db_module.build_run_store(), InMemoryRunStore)
        assert isinstance(db_module.build_task_store(), InMemoryTaskStore)

    def test_build_with_explicit_fallback(self):
        db_module.db_available = False
        fallback = InMemoryRunStore()
        assert db_module.build_run_store(fallback) is fallback
