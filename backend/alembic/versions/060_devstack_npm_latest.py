"""Add latest_package_version and claude_plugin install method.

Revision ID: 060_devstack_npm
Revises: 059_devstack_feat
"""

from alembic import op

revision = "060_devstack_npm"
down_revision = "059_devstack_feat"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries ADD COLUMN latest_package_version VARCHAR(50)"
    )
    op.execute(
        "ALTER TABLE devstack_entries DROP CONSTRAINT ck_devstack_entries_install_method"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD CONSTRAINT ck_devstack_entries_install_method "
        "CHECK (install_method IN ('github', 'npm', 'claude_plugin'))"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD CONSTRAINT ck_devstack_entries_claude_plugin_package "
        "CHECK (install_method != 'claude_plugin' OR package IS NOT NULL)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries DROP CONSTRAINT ck_devstack_entries_claude_plugin_package"
    )
    op.execute(
        "ALTER TABLE devstack_entries DROP CONSTRAINT ck_devstack_entries_install_method"
    )
    op.execute(
        "ALTER TABLE devstack_entries ADD CONSTRAINT ck_devstack_entries_install_method "
        "CHECK (install_method IN ('github', 'npm'))"
    )
    op.execute(
        "ALTER TABLE devstack_entries DROP COLUMN IF EXISTS latest_package_version"
    )
