"""Portfolio clients: add code + primary_contact (nullable)."""

from alembic import op

revision = "089_portfolio_client_fields"
down_revision = "088_portfolio_clients"


def upgrade() -> None:
    op.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS code varchar(255)")
    op.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS primary_contact varchar(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE clients DROP COLUMN IF EXISTS primary_contact")
    op.execute("ALTER TABLE clients DROP COLUMN IF EXISTS code")
