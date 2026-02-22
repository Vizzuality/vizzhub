"""Add ISO access review tables

Revision ID: 014_add_iso_access_tables
Revises: 013_add_manifest_path
Create Date: 2026-02-22

Tables: access_snapshots, access_reviews, access_review_actions
For ISO 27001 Google Workspace access review module.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

GEN_RANDOM_UUID = "gen_random_uuid()"

revision: str = "014_add_iso_access_tables"
down_revision: Union[str, None] = "013_add_manifest_path"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "access_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text(GEN_RANDOM_UUID)),
        sa.Column("provider", sa.String(50), nullable=False, index=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("data_version", sa.String(10), nullable=False, server_default="1"),
        sa.Column("source_metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("data", JSONB, nullable=False),
        sa.Column("summary", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "access_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text(GEN_RANDOM_UUID)),
        sa.Column("snapshot_id", UUID(as_uuid=True), sa.ForeignKey("access_snapshots.id"), nullable=False),
        sa.Column("previous_snapshot_id", UUID(as_uuid=True), sa.ForeignKey("access_snapshots.id"), nullable=True),
        sa.Column("reviewer_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("diff_summary", JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("signed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "access_review_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text(GEN_RANDOM_UUID)),
        sa.Column("review_id", UUID(as_uuid=True), sa.ForeignKey("access_reviews.id"), nullable=False),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.String(255), nullable=False),
        sa.Column("subject_label", sa.String(255), nullable=True),
        sa.Column("change_type", sa.String(50), nullable=False),
        sa.Column("previous_value", JSONB, nullable=True),
        sa.Column("current_value", JSONB, nullable=True),
        sa.Column("action_taken", sa.String(20), nullable=True),
        sa.Column("justification", sa.Text, nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("exception_until", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_access_reviews_snapshot_id", "access_reviews", ["snapshot_id"])
    op.create_index("ix_access_review_actions_review_id", "access_review_actions", ["review_id"])

    op.execute("""
        CREATE TRIGGER update_access_reviews_updated_at
        BEFORE UPDATE ON access_reviews
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("""
        CREATE TRIGGER update_access_review_actions_updated_at
        BEFORE UPDATE ON access_review_actions
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_access_review_actions_updated_at ON access_review_actions")
    op.execute("DROP TRIGGER IF EXISTS update_access_reviews_updated_at ON access_reviews")
    op.drop_index("ix_access_review_actions_review_id", table_name="access_review_actions")
    op.drop_index("ix_access_reviews_snapshot_id", table_name="access_reviews")
    op.drop_table("access_review_actions")
    op.drop_table("access_reviews")
    op.drop_table("access_snapshots")
