"""Add featured column to devstack_entries.

Revision ID: 059_devstack_feat
Revises: 058_devstack_sha
"""

from alembic import op

revision = "059_devstack_feat"
down_revision = "058_devstack_sha"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN featured BOOLEAN NOT NULL DEFAULT false"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries DROP COLUMN IF EXISTS featured"
    )
