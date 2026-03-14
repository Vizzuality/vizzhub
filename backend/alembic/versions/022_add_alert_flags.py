"""Add has_dependabot_alerts and has_budget_alerts to projects.

Revision ID: 022_alert_flags
Revises: 021_has_scorecard
Create Date: 2026-03-14

Default true for new projects. Sets false for VizzTracker imports.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022_alert_flags"
down_revision: Union[str, None] = "021_has_scorecard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "has_dependabot_alerts",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "has_budget_alerts",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.execute("UPDATE projects SET has_dependabot_alerts = false WHERE code IS NOT NULL")
    op.execute("UPDATE projects SET has_budget_alerts = false WHERE code IS NOT NULL")


def downgrade() -> None:
    op.drop_column("projects", "has_budget_alerts")
    op.drop_column("projects", "has_dependabot_alerts")
