"""Add iso_doc_notes table.

Revision ID: 053_iso_notes
Revises: 052_meta_instr
"""

from alembic import op

revision = "053_iso_notes"
down_revision = "052_meta_instr"


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS iso_doc_notes ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  node_id UUID NOT NULL REFERENCES iso_doc_nodes(id) ON DELETE CASCADE,"
        "  content TEXT NOT NULL,"
        "  done BOOLEAN NOT NULL DEFAULT false,"
        "  done_at TIMESTAMPTZ,"
        "  done_by_id UUID REFERENCES users(id) ON DELETE SET NULL,"
        "  created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_iso_doc_notes_node_id "
        "ON iso_doc_notes (node_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_iso_doc_notes_done_created "
        "ON iso_doc_notes (done, created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS iso_doc_notes")
