"""Add users table for Google SSO

Revision ID: 012_add_users_table
Revises: 011_add_slack_notifications
Create Date: 2026-02-04

This migration adds the users table for Google SSO authentication:
- Stores user info from Google (email, name, picture)
- Role-based access (user, admin)
- Tracks last login
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "012_add_users_table"
down_revision: Union[str, None] = "011_add_slack_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("picture", sa.String(500), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
