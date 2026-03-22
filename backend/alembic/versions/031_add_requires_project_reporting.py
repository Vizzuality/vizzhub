"""Add requires_project_reporting to users.

Revision ID: 031_add_requires_project_reporting
Revises: 030_add_rbac_tables
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "031_add_requires_proj_reporting"
down_revision: str = "030_add_rbac_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "requires_project_reporting",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "requires_project_reporting")
