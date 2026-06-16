"""SQLAlchemy ORM models for persistent agent state.

All models extend the shared ``Base`` plus ``UUIDMixin``/``TimestampMixin`` from
``shared_core.database`` so ids and timestamps are consistent across the
portfolio. These back the persistent stores in ``store_db.py``; the in-memory
fallbacks in ``store.py`` mirror the same fields.
"""

from shared_core.database import Base, TimestampMixin, UUIDMixin
from sqlalchemy import Column, Float, Integer, String, Text


class AgentRun(Base, UUIDMixin, TimestampMixin):
    """One end-to-end agent run, with its trace and cost summaries (as JSON)."""

    __tablename__ = "agent_runs"

    query = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    mode = Column(String(32), nullable=False, default="free_running")
    status = Column(String(32), nullable=False, default="completed", index=True)
    route = Column(String(32), nullable=True)
    trace_json = Column(Text, nullable=True)
    cost_json = Column(Text, nullable=True)


class MemoryMessage(Base, UUIDMixin, TimestampMixin):
    """A single role-tagged message belonging to a conversation session."""

    __tablename__ = "memory_messages"

    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False)
    seq = Column(Integer, nullable=False, default=0)


class ApprovalRecord(Base, UUIDMixin, TimestampMixin):
    """A pending/approved/rejected/expired approval for a risky tool call."""

    __tablename__ = "approvals"

    run_id = Column(String(64), nullable=True, index=True)
    action = Column(String(128), nullable=False)
    parameters_json = Column(Text, nullable=False, default="{}")
    status = Column(String(32), nullable=False, default="pending", index=True)
    reason = Column(Text, nullable=True)
    expires_at = Column(Float, nullable=False, default=0.0)
    decided_at = Column(Float, nullable=True)


class CreatedTask(Base, UUIDMixin, TimestampMixin):
    """A task persisted by the ``task_creator`` tool."""

    __tablename__ = "created_tasks"

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="open", index=True)
