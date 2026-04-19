"""Enforce unique project_id on devstack_project_contexts.

Revision ID: 063_devstack_projctx_uq
Revises: 062_devstack_proj_ctx
Create Date: 2026-04-19
"""

from alembic import op

revision = "063_devstack_projctx_uq"
down_revision = "062_devstack_proj_ctx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE devstack_project_contexts
                ADD CONSTRAINT uq_devstack_project_contexts_project_id UNIQUE (project_id);
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_project_contexts "
        "DROP CONSTRAINT IF EXISTS uq_devstack_project_contexts_project_id;"
    )
