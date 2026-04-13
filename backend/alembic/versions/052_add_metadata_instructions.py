"""Add instructions column to iso_doc_metadata.

Revision ID: 052_meta_instr
Revises: 051_cmd_queue
"""

from alembic import op

revision = "052_meta_instr"
down_revision = "051_cmd_queue"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE iso_doc_metadata "
        "ADD COLUMN IF NOT EXISTS instructions TEXT"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE iso_doc_metadata DROP COLUMN IF EXISTS instructions")
