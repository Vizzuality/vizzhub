"""Add has_scorecard flag to projects.

Revision ID: 021_has_scorecard
Revises: 020_status_migration
Create Date: 2026-03-14

Default true for new projects. Sets false for all projects imported
from VizzTracker (identified by having a code set). Production projects
that need scorecard will be manually enabled.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "021_has_scorecard"
down_revision: str | None = "020_status_migration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "has_scorecard",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    # Imported VizzTracker projects have a code; original vizzhub projects don't
    op.execute("UPDATE projects SET has_scorecard = false WHERE code IS NOT NULL")


def downgrade() -> None:
    op.drop_column("projects", "has_scorecard")
