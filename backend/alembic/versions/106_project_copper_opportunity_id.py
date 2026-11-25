"""Link projects to the Copper CRM opportunity they were created from.

Not unique: one contract can be tracked as several projects.

Revision ID: 106_project_copper_opp_id
Revises: 105_client_copper_company_id
"""

from collections.abc import Sequence

from alembic import op

revision: str = "106_project_copper_opp_id"
down_revision: str | None = "105_client_copper_company_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS copper_opportunity_id BIGINT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_projects_copper_opportunity_id "
        "ON projects (copper_opportunity_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_projects_copper_opportunity_id")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS copper_opportunity_id")
