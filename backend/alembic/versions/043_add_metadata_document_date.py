"""Add document_date to iso_doc_metadata.

Revision ID: 043_meta_date
Revises: 042_registries
"""

from alembic import op

revision = "043_meta_date"
down_revision = "042_registries"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE iso_doc_metadata ADD COLUMN document_date DATE"
    )
    op.execute(
        """
        UPDATE iso_doc_metadata
        SET document_date = (changelog->0->>'date')::date
        WHERE changelog IS NOT NULL
          AND jsonb_array_length(changelog) > 0
          AND changelog->0->>'date' IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE iso_doc_metadata DROP COLUMN IF EXISTS document_date")
