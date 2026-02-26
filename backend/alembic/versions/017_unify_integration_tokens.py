"""Unify integration tokens: create integration_settings, migrate slack_config

Revision ID: 017_unify_tokens
Revises: 016_encrypt_tokens
Create Date: 2026-02-26

Creates integration_settings table for key-value provider settings.
Migrates Slack data from slack_config to oauth_tokens (encrypted bot token)
and integration_settings (leadership_channel_id). Drops slack_config.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "017_unify_tokens"
down_revision: Union[str, None] = "016_encrypt_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create integration_settings table
    op.create_table(
        "integration_settings",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "provider", "key", name="uq_integration_settings_provider_key"
        ),
    )
    op.create_index(
        "ix_integration_settings_provider",
        "integration_settings",
        ["provider"],
    )

    # 2. Migrate data from slack_config
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT bot_token_encrypted, leadership_channel_id FROM slack_config")
    ).fetchall()

    for row in rows:
        bot_token = row[0]
        leadership_channel_id = row[1]

        if leadership_channel_id:
            conn.execute(
                sa.text(
                    "INSERT INTO integration_settings (id, provider, key, value) "
                    "VALUES (:id, :provider, :key, :value)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "provider": "slack",
                    "key": "leadership_channel_id",
                    "value": leadership_channel_id,
                },
            )

        if bot_token:
            from app.core.token_encryption import encrypt_token

            encrypted = encrypt_token(bot_token)
            now = datetime.now(timezone.utc)
            conn.execute(
                sa.text(
                    "INSERT INTO oauth_tokens "
                    "(id, provider, token_type, access_token, created_at, updated_at) "
                    "VALUES (:id, :provider, :token_type, :access_token, :created_at, :updated_at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "provider": "slack",
                    "token_type": "bot",
                    "access_token": encrypted,
                    "created_at": now,
                    "updated_at": now,
                },
            )

    # 3. Drop slack_config table
    op.drop_table("slack_config")


def downgrade() -> None:
    # Recreate slack_config (data is lost)
    op.create_table(
        "slack_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_token_encrypted", sa.Text(), nullable=True),
        sa.Column("leadership_channel_id", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Drop integration_settings
    op.drop_index("ix_integration_settings_provider", table_name="integration_settings")
    op.drop_table("integration_settings")
