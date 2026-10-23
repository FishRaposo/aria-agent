"""Persist connected sessions, skill evidence, and approval outcomes.

Revision ID: 0003_connected_app
Revises: 0002_execution_claim

Historical rows deliberately retain NULL context/session: absence is unknown,
not fabricated evidence of execution or skill use.
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_connected_app"
down_revision = "0002_execution_claim"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("session_id", sa.String(64), nullable=True))
    op.add_column(
        "agent_runs", sa.Column("skill_context_json", sa.Text(), nullable=True)
    )
    op.add_column("agent_runs", sa.Column("approval_id", sa.String(64), nullable=True))
    op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
    op.create_index("ix_agent_runs_approval_id", "agent_runs", ["approval_id"])
    op.add_column("approvals", sa.Column("execution_result", sa.Text(), nullable=True))
    op.add_column(
        "approvals", sa.Column("execution_trace_json", sa.Text(), nullable=True)
    )
    op.add_column(
        "memory_messages", sa.Column("event_key", sa.String(200), nullable=True)
    )
    op.create_index(
        "uq_memory_messages_event_key", "memory_messages", ["event_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_memory_messages_event_key", table_name="memory_messages")
    op.drop_column("memory_messages", "event_key")
    for column in ("execution_trace_json", "execution_result"):
        op.drop_column("approvals", column)
    op.drop_index("ix_agent_runs_approval_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_session_id", table_name="agent_runs")
    for column in ("approval_id", "skill_context_json", "session_id"):
        op.drop_column("agent_runs", column)
