"""Add project status column

Revision ID: 002_add_project_status
Revises: 001_add_oauth_tokens
Create Date: 2026-01-25

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_add_project_status"
down_revision: str | None = "c5597ce1022c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
    )


def downgrade() -> None:
    op.drop_column("projects", "status")
