"""Create iso_doc_nodes, iso_doc_versions, iso_doc_metadata tables.

Revision ID: 039_iso_docs
Revises: 038_pb_publish_log
"""

from alembic import op

revision = "039_iso_docs"
down_revision = "038_pb_publish_log"


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE iso_doc_node_type AS ENUM ('page', 'group');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;

        DO $$ BEGIN
            CREATE TYPE iso_doc_category AS ENUM (
                'manual', 'policy', 'procedure', 'plan', 'record', 'report'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;

        DO $$ BEGIN
            CREATE TYPE iso_doc_status AS ENUM ('draft', 'approved', 'under_review');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;

        CREATE TABLE IF NOT EXISTS iso_doc_nodes (
            id UUID PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            slug VARCHAR(255) NOT NULL,
            type iso_doc_node_type NOT NULL,
            parent_id UUID REFERENCES iso_doc_nodes(id) ON DELETE CASCADE,
            position INTEGER NOT NULL DEFAULT 0,
            created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            updated_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_iso_doc_nodes_parent_slug UNIQUE (parent_id, slug)
        );

        CREATE TABLE IF NOT EXISTS iso_doc_versions (
            id UUID PRIMARY KEY,
            node_id UUID NOT NULL REFERENCES iso_doc_nodes(id) ON DELETE CASCADE,
            content TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL,
            created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_iso_doc_versions_node_version UNIQUE (node_id, version)
        );

        CREATE TABLE IF NOT EXISTS iso_doc_metadata (
            id UUID PRIMARY KEY,
            node_id UUID NOT NULL UNIQUE REFERENCES iso_doc_nodes(id) ON DELETE CASCADE,
            code VARCHAR(50),
            standard VARCHAR[] ,
            clauses VARCHAR[],
            category iso_doc_category,
            doc_version VARCHAR(20),
            status iso_doc_status,
            original_filename VARCHAR(500),
            changelog JSONB,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            CONSTRAINT uq_iso_doc_metadata_node UNIQUE (node_id)
        );
    """)


def downgrade() -> None:
    op.execute("""
        DROP TABLE IF EXISTS iso_doc_metadata;
        DROP TABLE IF EXISTS iso_doc_versions;
        DROP TABLE IF EXISTS iso_doc_nodes;
        DROP TYPE IF EXISTS iso_doc_status;
        DROP TYPE IF EXISTS iso_doc_category;
        DROP TYPE IF EXISTS iso_doc_node_type;
    """)
