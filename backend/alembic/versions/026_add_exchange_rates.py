"""Add exchange_rates table for ECB daily rates.

Revision ID: 026_add_exchange_rates
Revises: 025_move_budget_to_projects
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026_add_exchange_rates"
down_revision: str = "025_move_budget_to_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "rate_date", "currency_code", name="uq_exchange_rates_date_currency"
        ),
    )
    op.create_index(
        "ix_exchange_rates_currency_date",
        "exchange_rates",
        ["currency_code", "rate_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_exchange_rates_currency_date", table_name="exchange_rates")
    op.drop_table("exchange_rates")
