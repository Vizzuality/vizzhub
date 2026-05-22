"""Create accrual_periods table.

Revision ID: 078_create_accrual_periods
Revises: 077_project_locked_fx_rate
Create Date: 2026-05-22 00:00:01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "078_create_accrual_periods"
down_revision: str | None = "077_project_locked_fx_rate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accrual_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column(
            "fx_rates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("start_date", name="uq_accrual_periods_start_date"),
    )
    op.execute(
        "ALTER TABLE accrual_periods ADD CONSTRAINT ck_accrual_periods_closed_status_consistent "
        "CHECK ((closed_at IS NULL) = (status = 'open'))"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_accrual_periods_one_open "
        "ON accrual_periods (status) WHERE status = 'open'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_accrual_periods_one_open")
    op.drop_table("accrual_periods")
