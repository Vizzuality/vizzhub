"""Add default_sort_key to registry_types."""

revision = "046_reg_default_sort"
down_revision = "045_attach_node_id"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.execute(
        "ALTER TABLE registry_types ADD COLUMN IF NOT EXISTS "
        "default_sort_key VARCHAR(100)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE registry_types DROP COLUMN IF EXISTS default_sort_key")
