"""Flag internal programs (ops/admin buckets) to keep them out of the portfolio.

Revision ID: 100_program_is_internal
Revises: 099_portfolio_search_vector
"""

from alembic import op

revision = "100_program_is_internal"
down_revision = "099_portfolio_search_vector"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE programs ADD COLUMN IF NOT EXISTS is_internal boolean NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE programs DROP COLUMN IF EXISTS is_internal")
