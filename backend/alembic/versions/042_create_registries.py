"""Create registry tables for ISO Docs.

Revision ID: 042_registries
Revises: 041_drive_map
"""

from alembic import op

revision = "042_registries"
down_revision = "041_drive_map"


def upgrade() -> None:
    op.execute("ALTER TYPE iso_doc_node_type ADD VALUE IF NOT EXISTS 'registry'")

    op.execute("""
        CREATE TABLE IF NOT EXISTS registry_types (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255) NOT NULL UNIQUE,
            description TEXT,
            is_yearly BOOLEAN NOT NULL DEFAULT false,
            schema JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            updated_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS registry_rows (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            node_id UUID NOT NULL REFERENCES iso_doc_nodes(id) ON DELETE CASCADE,
            year INTEGER,
            row_index INTEGER NOT NULL DEFAULT 0,
            data JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            updated_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_registry_rows_node_year "
        "ON registry_rows(node_id, year)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS registry_attachments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            row_id UUID NOT NULL REFERENCES registry_rows(id) ON DELETE CASCADE,
            field_key VARCHAR(255),
            filename VARCHAR(500) NOT NULL,
            s3_key VARCHAR(1000) NOT NULL,
            content_type VARCHAR(100) NOT NULL,
            size_bytes INTEGER NOT NULL,
            uploaded_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute(
        "ALTER TABLE iso_doc_nodes "
        "ADD COLUMN IF NOT EXISTS registry_type_id UUID "
        "REFERENCES registry_types(id) ON DELETE SET NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE iso_doc_nodes DROP COLUMN IF EXISTS registry_type_id")
    op.execute("DROP TABLE IF EXISTS registry_attachments")
    op.execute("DROP TABLE IF EXISTS registry_rows")
    op.execute("DROP TABLE IF EXISTS registry_types")
