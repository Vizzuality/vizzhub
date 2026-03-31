"""Add classification column to iso_doc_metadata.

Revision ID: 040_classification
Revises: 039_iso_docs
"""

from alembic import op

revision = "040_classification"
down_revision = "039_iso_docs"


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE iso_doc_classification AS ENUM ('internal_use', 'confidential');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        ALTER TABLE iso_doc_metadata
        ADD COLUMN IF NOT EXISTS classification iso_doc_classification
        NOT NULL DEFAULT 'internal_use'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE iso_doc_metadata DROP COLUMN IF EXISTS classification")
    op.execute("DROP TYPE IF EXISTS iso_doc_classification")
