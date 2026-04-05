"""Add widget node type and widget_key column.

Revision ID: 047
Revises: 046
"""

from alembic import op

revision = "047_widget_node_type"
down_revision = "046_reg_default_sort"


def upgrade() -> None:
    op.execute("ALTER TYPE iso_doc_node_type ADD VALUE IF NOT EXISTS 'widget'")
    op.execute(
        "ALTER TABLE iso_doc_nodes ADD COLUMN IF NOT EXISTS widget_key VARCHAR(100)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE iso_doc_nodes DROP COLUMN IF EXISTS widget_key")
