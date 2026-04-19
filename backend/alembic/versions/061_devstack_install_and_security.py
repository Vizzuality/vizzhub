"""Add install metrics + npm vulnerability/deprecation columns.

Revision ID: 061_devstack_inst
Revises: 060_devstack_npm
"""

from alembic import op

revision = "061_devstack_inst"
down_revision = "060_devstack_npm"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN install_count INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN last_installed_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN deprecated BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN deprecation_message TEXT"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN vulnerabilities JSONB"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN vulnerabilities_checked_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS vulnerabilities_checked_at")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS vulnerabilities")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS deprecation_message")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS deprecated")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS last_installed_at")
    op.execute("ALTER TABLE devstack_entries DROP COLUMN IF EXISTS install_count")
