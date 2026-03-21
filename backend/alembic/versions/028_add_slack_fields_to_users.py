"""Add slack_user_id and slack_display_name to users.

Revision ID: 028_add_slack_fields_to_users
Revises: 027_add_invoice_postponements
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "028_add_slack_fields_to_users"
down_revision: str = "027_add_invoice_postponements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("slack_user_id", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("slack_display_name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "slack_display_name")
    op.drop_column("users", "slack_user_id")
