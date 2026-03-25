"""Add playbook_editor role.

Revision ID: 035_add_playbook_editor
Revises: 034_create_playbook
"""

from alembic import op
import sqlalchemy as sa

revision = "035_add_playbook_editor"
down_revision = "034_create_playbook"


def upgrade() -> None:
    op.execute("INSERT INTO roles (id, name) VALUES (gen_random_uuid(), 'playbook_editor')")


def downgrade() -> None:
    op.execute("DELETE FROM user_roles WHERE role_id IN (SELECT id FROM roles WHERE name = 'playbook_editor')")
    op.execute("DELETE FROM roles WHERE name = 'playbook_editor'")
