"""ARIA database availability probe and store selection.

On startup we probe the configured database with a short connect timeout; if it
is reachable, agent runs, tasks, approvals, and memory persist to PostgreSQL and
survive restarts. If the database is unavailable — or its driver is not
installed, which is the offline-first default for tests and the demo — we
transparently fall back to in-memory stores so the service still runs with NO
database.

The ``DatabaseManager`` (and thus the DB driver import) is created lazily inside
``check_db`` so merely importing this module never requires a Postgres driver.
"""

from typing import Optional

from loguru import logger
from sqlalchemy import text

from .config import AppConfig
from .store import (
    DEFAULT_APPROVAL_TIMEOUT,
    InMemoryApprovalStore,
    InMemoryRunStore,
    InMemoryTaskStore,
)
from .store_db import DatabaseApprovalStore, DatabaseRunStore, DatabaseTaskStore

config = AppConfig()

db_manager = None  # lazily constructed in check_db()
db_available: bool = False


def _get_manager():
    """Lazily build the shared DatabaseManager (imports the DB driver)."""
    global db_manager
    if db_manager is None:
        from aria.internal.vendor_core.database import DatabaseManager

        db_manager = DatabaseManager(
            config.DATABASE_URL,
            pool_size=config.DB_POOL_SIZE,
            max_overflow=config.DB_MAX_OVERFLOW,
            pool_timeout=min(config.DB_POOL_TIMEOUT, config.DB_PROBE_TIMEOUT),
        )
    return db_manager


def _probe_connectivity() -> None:
    """Open a single connection with a short connect timeout (fail-fast probe).

    Uses a throwaway engine so an unreachable Postgres returns within
    ``DB_PROBE_TIMEOUT`` seconds instead of hanging on the default driver
    timeout. SQLite URLs (used in tests) ignore the connect timeout harmlessly.
    """
    from sqlalchemy import create_engine

    url = config.DATABASE_URL
    connect_args: dict = {}
    if "sqlite" not in url:
        # psycopg / asyncpg both honour a ``connect_timeout`` connect arg.
        connect_args["connect_timeout"] = int(config.DB_PROBE_TIMEOUT)
    probe_engine = create_engine(url, connect_args=connect_args)
    try:
        with probe_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        probe_engine.dispose()


def check_db() -> bool:
    """Probe database connectivity and cache the result in ``db_available``.

    Returns ``False`` (and logs a warning) if the driver is missing or the
    database is unreachable within the probe timeout, so callers fall back to
    the in-memory stores.
    """
    global db_available
    # Ensure models are imported so create_tables() sees every table.
    from . import models  # noqa: F401

    try:
        _probe_connectivity()
        _get_manager().create_tables()
        db_available = True
        logger.info("Database connected — agent state will persist to PostgreSQL.")
    except Exception as exc:
        db_available = False
        logger.warning(
            "Database unavailable — falling back to in-memory stores: {}", exc
        )
    return db_available


def build_run_store(fallback: Optional[InMemoryRunStore] = None):
    """Return the active run store based on the last probe result."""
    if db_available and db_manager is not None:
        return DatabaseRunStore(db_manager.get_session)
    return fallback or InMemoryRunStore()


def build_task_store(fallback: Optional[InMemoryTaskStore] = None):
    """Return the active task store based on the last probe result."""
    if db_available and db_manager is not None:
        return DatabaseTaskStore(db_manager.get_session)
    return fallback or InMemoryTaskStore()


def build_approval_store(
    fallback: Optional[InMemoryApprovalStore] = None,
    timeout: float = DEFAULT_APPROVAL_TIMEOUT,
):
    """Return the active approval store based on the last probe result."""
    if db_available and db_manager is not None:
        return DatabaseApprovalStore(db_manager.get_session, timeout=timeout)
    return fallback or InMemoryApprovalStore(timeout=timeout)
