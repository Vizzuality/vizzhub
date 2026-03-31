"""Create iso_doc_drive_mappings table.

Revision ID: 041_drive_map
Revises: 040_classification
"""

from alembic import op

revision = "041_drive_map"
down_revision = "040_classification"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS iso_doc_drive_mappings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            node_id UUID NOT NULL
                REFERENCES iso_doc_nodes(id) ON DELETE CASCADE,
            drive_file_id VARCHAR(255) NOT NULL,
            drive_file_type VARCHAR(20) NOT NULL,
            last_exported_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_iso_doc_drive_mapping_node UNIQUE (node_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS iso_doc_drive_mappings")
