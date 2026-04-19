"""Add devstack_project_contexts table.

Revision ID: 062_devstack_proj_ctx
Revises: 061_devstack_inst
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "062_devstack_proj_ctx"
down_revision = "061_devstack_inst"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
            FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE RESTRICT
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_devstack_project_contexts_slug
        ON devstack_project_contexts (slug)
    """)


def downgrade() -> None:
    op.drop_index(
        "ix_devstack_project_contexts_slug",
        table_name="devstack_project_contexts",
    )
    op.drop_table("devstack_project_contexts")
