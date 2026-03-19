"""Add oauth_states table for CSRF protection

Revision ID: 015_add_oauth_states
Revises: 014_add_iso_access_tables
Create Date: 2026-02-26

Replaces in-memory OAuthStateManager._states dict with DB table
for multi-worker support.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015_add_oauth_states"
down_revision: str | None = "014_add_iso_access_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(64), primary_key=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("oauth_states")
