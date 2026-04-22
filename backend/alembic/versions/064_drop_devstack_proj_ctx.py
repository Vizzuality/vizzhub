"""Drop devstack_project_contexts table.

Revision ID: 064_drop_devstack_ctx
Revises: 063_devstack_projctx_uq
Create Date: 2026-04-22
"""

from alembic import op


revision = "064_drop_devstack_ctx"
down_revision = "063_devstack_projctx_uq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS devstack_project_contexts CASCADE")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS devstack_project_contexts (
            id UUID DEFAULT gen_random_uuid() NOT NULL,
            slug VARCHAR(64) NOT NULL,
            project_id UUID NOT NULL,
            description TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            CONSTRAINT uq_devstack_project_contexts_slug UNIQUE (slug),
            CONSTRAINT uq_devstack_project_contexts_project_id UNIQUE (project_id),
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_devstack_project_contexts_slug
        ON devstack_project_contexts (slug)
    """)
