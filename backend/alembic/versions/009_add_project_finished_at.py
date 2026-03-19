"""Add finished_at column to projects

Revision ID: 009_add_project_finished_at
Revises: 008_add_jobs_table
Create Date: 2026-02-02

This migration adds finished_at to track when a project was actually
marked as finished (separate from end_date which is the contract date).
The timeline stops at finished_at when set.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009_add_project_finished_at"
down_revision: str | None = "008_add_jobs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("finished_at", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "finished_at")
