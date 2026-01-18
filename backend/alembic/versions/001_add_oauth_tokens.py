"""Add OAuth tokens table

Revision ID: 001_add_oauth_tokens
Revises: 000_initial_schema
Create Date: 2026-01-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001_add_oauth_tokens"
down_revision: Union[str, None] = "000_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oauth_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(50), nullable=False, server_default="Bearer"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("cloud_id", sa.String(255), nullable=True),
        sa.Column("site_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create index on provider for faster lookups
    op.create_index("ix_oauth_tokens_provider", "oauth_tokens", ["provider"])

    # Create trigger for updated_at
    op.execute("""
        CREATE TRIGGER update_oauth_tokens_updated_at
        BEFORE UPDATE ON oauth_tokens
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS update_oauth_tokens_updated_at ON oauth_tokens")
    op.drop_index("ix_oauth_tokens_provider", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")
