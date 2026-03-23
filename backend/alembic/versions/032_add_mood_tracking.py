"""Add mood tracking: mood/feedback_text to reports, anonymous_feedback table.

Revision ID: 032_add_mood_tracking
Revises: 031_add_requires_proj_reporting
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "032_add_mood_tracking"
down_revision: str = "031_add_requires_proj_reporting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("mood", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("feedback_text", sa.Text(), nullable=True))

    op.create_table(
        "anonymous_feedback",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(2000), nullable=False),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("anonymous_feedback")
    op.drop_column("reports", "feedback_text")
    op.drop_column("reports", "mood")
