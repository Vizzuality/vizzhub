"""Add github_sha column to devstack_entries.

Revision ID: 058_devstack_sha
Revises: 057_devstack
"""

from alembic import op

revision = "058_devstack_sha"
down_revision = "057_devstack"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN github_sha VARCHAR(40)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries DROP COLUMN IF EXISTS github_sha"
    )
