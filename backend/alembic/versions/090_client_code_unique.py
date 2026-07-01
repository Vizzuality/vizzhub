"""Portfolio clients: partial unique index on code (WHERE code IS NOT NULL)."""

from alembic import op

revision = "090_client_code_unique"
down_revision = "089_portfolio_client_fields"


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_code "
        "ON clients (code) WHERE code IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_clients_code")
