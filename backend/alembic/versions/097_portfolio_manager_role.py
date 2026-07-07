"""Create the portfolio_manager role.

Revision ID: 097_portfolio_manager_role
Revises: 096_portfolio_program_rollup
"""

from alembic import op

revision = "097_portfolio_manager_role"
down_revision = "096_portfolio_program_rollup"


def upgrade() -> None:
    op.execute(
        "INSERT INTO roles (id, name)"
        " VALUES (gen_random_uuid(), 'portfolio_manager')"
        " ON CONFLICT (name) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE name = 'portfolio_manager'")
