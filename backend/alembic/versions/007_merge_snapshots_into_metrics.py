"""Merge metric_snapshots into metrics table

Revision ID: 007_merge_snapshots_into_metrics
Revises: 006_snapshot_type_constraint
Create Date: 2026-01-30

This migration:
1. Adds period_year, period_month, snapshot_type, weights_applied, targets_applied to metrics
2. Migrates data from metric_snapshots to the corresponding metrics records
3. Deletes orphaned metrics records (not referenced by any snapshot)
4. Adds unique constraint (project_id, period_year, period_month, snapshot_type)
5. Drops metric_snapshots table

This simplifies the data model from 2 tables to 1, with clear uniqueness rules.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "007_merge_snapshots_into_metrics"
down_revision: Union[str, None] = "006_snapshot_type_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add new columns to metrics table
    op.add_column("metrics", sa.Column("period_year", sa.Integer(), nullable=True))
    op.add_column("metrics", sa.Column("period_month", sa.Integer(), nullable=True))
    op.add_column(
        "metrics",
        sa.Column("snapshot_type", sa.String(20), nullable=True),
    )
    op.add_column("metrics", sa.Column("weights_applied", JSONB(), nullable=True))
    op.add_column("metrics", sa.Column("targets_applied", JSONB(), nullable=True))

    # Step 2: Migrate data from metric_snapshots to metrics
    # Update metrics records that are referenced by snapshots
    op.execute("""
        UPDATE metrics m
        SET
            period_year = ms.period_year,
            period_month = ms.period_month,
            snapshot_type = ms.snapshot_type,
            weights_applied = ms.weights_applied,
            targets_applied = ms.targets_applied
        FROM metric_snapshots ms
        WHERE m.id = ms.metrics_id
    """)

    # Step 3: Delete orphaned metrics records (not referenced by any snapshot)
    op.execute("""
        DELETE FROM metrics
        WHERE id NOT IN (SELECT metrics_id FROM metric_snapshots)
    """)

    # Step 4: Make snapshot columns NOT NULL for remaining records
    # First set defaults for any NULL values (shouldn't happen after migration)
    op.execute("""
        UPDATE metrics
        SET
            period_year = EXTRACT(YEAR FROM period_end)::integer,
            period_month = EXTRACT(MONTH FROM period_end)::integer,
            snapshot_type = 'punctual',
            weights_applied = '{}',
            targets_applied = '{}'
        WHERE period_year IS NULL
    """)

    # Step 5: Alter columns to NOT NULL
    op.alter_column("metrics", "period_year", nullable=False)
    op.alter_column("metrics", "period_month", nullable=False)
    op.alter_column("metrics", "snapshot_type", nullable=False)
    op.alter_column("metrics", "weights_applied", nullable=False)
    op.alter_column("metrics", "targets_applied", nullable=False)

    # Step 6: Add CHECK constraint for valid snapshot_type values
    op.execute("""
        ALTER TABLE metrics
        ADD CONSTRAINT chk_metrics_snapshot_type
        CHECK (snapshot_type IN ('punctual', 'cumulative'))
    """)

    # Step 7: Add unique constraint
    op.create_index(
        "uq_metrics_project_period_type",
        "metrics",
        ["project_id", "period_year", "period_month", "snapshot_type"],
        unique=True,
    )

    # Step 8: Drop metric_snapshots table
    op.drop_index("uq_snapshot_project_month_type", table_name="metric_snapshots")
    op.drop_index("idx_snapshot_project_period", table_name="metric_snapshots")
    op.drop_table("metric_snapshots")


def downgrade() -> None:
    # Recreate metric_snapshots table
    op.create_table(
        "metric_snapshots",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "metrics_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("metrics.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer(), nullable=False),
        sa.Column("snapshot_type", sa.String(20), nullable=False, server_default="punctual"),
        sa.Column("weights_applied", JSONB(), nullable=False),
        sa.Column("targets_applied", JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Recreate indexes
    op.create_index(
        "idx_snapshot_project_period",
        "metric_snapshots",
        ["project_id", "period_year", "period_month"],
    )
    op.create_index(
        "uq_snapshot_project_month_type",
        "metric_snapshots",
        ["project_id", "period_year", "period_month", "snapshot_type"],
        unique=True,
    )

    # Migrate data back from metrics to metric_snapshots
    op.execute("""
        INSERT INTO metric_snapshots (project_id, metrics_id, period_year, period_month, snapshot_type, weights_applied, targets_applied)
        SELECT project_id, id, period_year, period_month, snapshot_type, weights_applied, targets_applied
        FROM metrics
        WHERE period_year IS NOT NULL
    """)

    # Drop unique constraint from metrics
    op.drop_index("uq_metrics_project_period_type", table_name="metrics")

    # Drop CHECK constraint
    op.execute("ALTER TABLE metrics DROP CONSTRAINT IF EXISTS chk_metrics_snapshot_type")

    # Drop new columns from metrics
    op.drop_column("metrics", "targets_applied")
    op.drop_column("metrics", "weights_applied")
    op.drop_column("metrics", "snapshot_type")
    op.drop_column("metrics", "period_month")
    op.drop_column("metrics", "period_year")
