"""Merge adjusted_days into days and drop the column.

Revision ID: 023_merge_adjusted_days
Revises: 022_alert_flags
Create Date: 2026-03-19

For rows where adjusted_days is set, it replaces days (not additive).
days is widened to Numeric(8,2) to preserve decimal precision, then
adjusted_days is merged and dropped.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "023_merge_adjusted_days"
down_revision: str = "022_alert_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "budget_lines",
        "days",
        type_=sa.Numeric(8, 2),
        existing_type=sa.Integer(),
        existing_nullable=True,
        postgresql_using="days::numeric(8,2)",
    )
    op.execute(
        "UPDATE budget_lines SET days = adjusted_days "
        "WHERE adjusted_days IS NOT NULL"
    )
    op.drop_column("budget_lines", "adjusted_days")


def downgrade() -> None:
    op.add_column(
        "budget_lines",
        sa.Column("adjusted_days", sa.Numeric(8, 2), nullable=True),
    )
    op.alter_column(
        "budget_lines",
        "days",
        type_=sa.Integer(),
        existing_type=sa.Numeric(8, 2),
        existing_nullable=True,
        postgresql_using="days::integer",
    )
