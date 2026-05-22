"""Add locked_fx_rate column to projects.

Revision ID: 077_project_locked_fx_rate
Revises: 076_invoice_alert_definitions
Create Date: 2026-05-22 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "077_project_locked_fx_rate"
down_revision: str | None = "076_invoice_alert_definitions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("locked_fx_rate", sa.Numeric(12, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "locked_fx_rate")
