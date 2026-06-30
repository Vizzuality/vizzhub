"""Portfolio clients table + projects.client_id FK."""

from alembic import op

revision = "088_portfolio_clients"
down_revision = "087_portfolio_taxonomy"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id uuid PRIMARY KEY,
            name varchar(255) NOT NULL,
            slug varchar(255) NOT NULL UNIQUE,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_id uuid "
        "REFERENCES clients(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_projects_client_id ON projects (client_id)")


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS client_id")
    op.execute("DROP TABLE IF EXISTS clients")
