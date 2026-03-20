"""Move budget from tracker_project_settings to projects.

Budget is a core project attribute. Scorecard's metrics.budget_total
is kept as a denormalized copy for the scoring pipeline.

Revision ID: 025_move_budget_to_projects
Revises: 024_move_currency_to_projects
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025_move_budget_to_projects"
down_revision: str = "024_move_currency_to_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add budget column to projects
    op.add_column(
        "projects",
        sa.Column("budget", sa.Numeric(12, 2), nullable=True),
    )

    # Migrate from tracker_project_settings (primary source)
    op.execute("""
        UPDATE projects p
        SET budget = s.budget
        FROM tracker_project_settings s
        WHERE p.id = s.project_id
          AND s.budget IS NOT NULL
    """)

    # Fallback: migrate from metrics.budget_total (latest per project)
    op.execute("""
        UPDATE projects p
        SET budget = sub.budget_total
        FROM (
            SELECT DISTINCT ON (project_id) project_id, budget_total
            FROM metrics
            WHERE budget_total IS NOT NULL
            ORDER BY project_id, period_year DESC, period_month DESC
        ) sub
        WHERE p.id = sub.project_id
          AND p.budget IS NULL
    """)

    # Drop budget from tracker_project_settings
    op.drop_column("tracker_project_settings", "budget")


def downgrade() -> None:
    op.add_column(
        "tracker_project_settings",
        sa.Column("budget", sa.Numeric(12, 2), nullable=True),
    )
    # Copy budget back
    op.execute("""
        UPDATE tracker_project_settings s
        SET budget = p.budget
        FROM projects p
        WHERE s.project_id = p.id
          AND p.budget IS NOT NULL
    """)
    op.drop_column("projects", "budget")
