"""Add comment column to capacity_plans.

Revision ID: 054_planner_cmt
Revises: 053_iso_notes
"""

from alembic import op

revision = "054_planner_cmt"
down_revision = "053_iso_notes"


def upgrade() -> None:
    op.execute("ALTER TABLE capacity_plans ADD COLUMN IF NOT EXISTS comment TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE capacity_plans DROP COLUMN IF EXISTS comment")
