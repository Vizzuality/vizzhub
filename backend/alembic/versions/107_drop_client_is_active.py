"""Drop clients.is_active: merged and unused clients are now deleted.

Copper is the client catalogue, so VizzHub keeps only clients with projects
and has no use for a dormant state.

Revision ID: 107_drop_client_is_active
Revises: 106_project_copper_opp_id
"""

from collections.abc import Sequence

from alembic import op

revision: str = "107_drop_client_is_active"
down_revision: str | None = "106_project_copper_opp_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE clients DROP COLUMN IF EXISTS is_active")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true"
    )
