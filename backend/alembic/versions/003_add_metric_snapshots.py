"""Add metric snapshots table

Revision ID: 003_add_metric_snapshots
Revises: 002_add_project_status
Create Date: 2026-01-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "003_add_metric_snapshots"
down_revision: str | None = "002_add_project_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_snapshots",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metrics_id",
            UUID(as_uuid=True),
            sa.ForeignKey("metrics.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("snapshot_type", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("weights_applied", JSONB(), nullable=False),
        sa.Column("targets_applied", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "idx_snapshot_project_period",
        "metric_snapshots",
        ["project_id", "period_year", "period_month"],
    )

    op.create_index(
        "uq_snapshot_project_month",
        "metric_snapshots",
        ["project_id", "period_year", "period_month"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_snapshot_project_month", table_name="metric_snapshots")
    op.drop_index("idx_snapshot_project_period", table_name="metric_snapshots")
    op.drop_table("metric_snapshots")
