"""Add snapshot type constraint and update unique index

Revision ID: 006_snapshot_type_constraint
Revises: 005_recreate_metric_snapshots
Create Date: 2026-01-30

Changes:
1. Add CHECK constraint for valid snapshot_type values ('punctual', 'cumulative')
2. Change unique constraint from (project_id, year, month)
   to (project_id, year, month, snapshot_type)
3. Migrate existing data: 'monthly'/'captured'/'manual' -> 'punctual'

This allows ONE punctual and ONE cumulative snapshot per project per month.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "006_snapshot_type_constraint"
down_revision: Union[str, None] = "005_recreate_metric_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Migrate existing snapshot_type values to 'punctual'
    op.execute("""
        UPDATE metric_snapshots
        SET snapshot_type = 'punctual'
        WHERE snapshot_type IN ('monthly', 'captured', 'manual')
           OR snapshot_type IS NULL
    """)

    # Step 2: Drop existing unique index
    op.drop_index("uq_snapshot_project_month", table_name="metric_snapshots")

    # Step 3: Add CHECK constraint for valid snapshot_type values
    op.execute("""
        ALTER TABLE metric_snapshots
        ADD CONSTRAINT chk_snapshot_type
        CHECK (snapshot_type IN ('punctual', 'cumulative'))
    """)

    # Step 4: Create new unique index including snapshot_type
    op.create_index(
        "uq_snapshot_project_month_type",
        "metric_snapshots",
        ["project_id", "period_year", "period_month", "snapshot_type"],
        unique=True,
    )


def downgrade() -> None:
    # Step 1: Drop new unique index
    op.drop_index("uq_snapshot_project_month_type", table_name="metric_snapshots")

    # Step 2: Drop CHECK constraint
    op.execute("""
        ALTER TABLE metric_snapshots
        DROP CONSTRAINT IF EXISTS chk_snapshot_type
    """)

    # Step 3: Recreate original unique index
    op.create_index(
        "uq_snapshot_project_month",
        "metric_snapshots",
        ["project_id", "period_year", "period_month"],
        unique=True,
    )
