"""Add tsvector column and GIN index for ISO doc full-text search.

Revision ID: 048_fts_search_vector
Revises: 047_widget_node_type
"""

from alembic import op

revision = "048_fts_search_vector"
down_revision = "047_widget_node_type"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE iso_doc_versions "
        "ADD COLUMN IF NOT EXISTS search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_iso_doc_versions_search_vector "
        "ON iso_doc_versions USING gin(search_vector)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_iso_doc_versions_search_vector")
    op.execute("ALTER TABLE iso_doc_versions DROP COLUMN IF EXISTS search_vector")
