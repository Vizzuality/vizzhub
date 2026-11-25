"""Link clients to their Copper CRM company.

Revision ID: 105_client_copper_company_id
Revises: 104_cerebro_read_role
"""

from collections.abc import Sequence

from alembic import op

revision: str = "105_client_copper_company_id"
down_revision: str | None = "104_cerebro_read_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE clients ADD COLUMN IF NOT EXISTS copper_company_id BIGINT")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_copper_company_id "
        "ON clients (copper_company_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_clients_copper_company_id")
    op.execute("ALTER TABLE clients DROP COLUMN IF EXISTS copper_company_id")
