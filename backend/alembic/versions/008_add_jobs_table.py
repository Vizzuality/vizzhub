"""Add jobs table for async task tracking

Revision ID: 008_add_jobs_table
Revises: 007_merge_snapshots_into_metrics
Create Date: 2026-02-01

This migration adds the jobs table to track async tasks like historical
metrics capture. Jobs store progress, results, and error information.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "008_add_jobs_table"
down_revision: str | None = "007_merge_snapshots_into_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("params", JSONB(), nullable=False, server_default="{}"),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(500), nullable=True),
        sa.Column("logs", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("error_traceback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arq_job_id", sa.String(100), nullable=True),
    )

    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_project_id", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
