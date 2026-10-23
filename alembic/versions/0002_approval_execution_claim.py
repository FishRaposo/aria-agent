"""Add immutable approval binding and durable single-use execution claims.

Revision ID: 0002_execution_claim
Revises: 0001_initial

Existing approvals deliberately keep a NULL binding: they need fresh review
instead of acquiring execution authority through an inferred backfill.
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_execution_claim"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("approvals", sa.Column("binding_hash", sa.String(64), nullable=True))
    op.add_column(
        "approvals", sa.Column("execution_token", sa.String(32), nullable=True)
    )
    op.add_column(
        "approvals", sa.Column("execution_status", sa.String(32), nullable=True)
    )
    op.add_column(
        "approvals", sa.Column("execution_claimed_at", sa.Float(), nullable=True)
    )
    op.add_column(
        "approvals", sa.Column("execution_completed_at", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    for column in (
        "execution_completed_at",
        "execution_claimed_at",
        "execution_status",
        "execution_token",
        "binding_hash",
    ):
        op.drop_column("approvals", column)
