"""Encrypt existing plaintext OAuth tokens

Revision ID: 016_encrypt_tokens
Revises: 015_add_oauth_states
Create Date: 2026-02-26

One-time migration: reads existing oauth_tokens rows and encrypts
access_token and refresh_token using OAUTH_ENCRYPTION_KEY.
Requires the env var to be set before running.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

revision: str = "016_encrypt_tokens"
down_revision: Union[str, None] = "015_add_oauth_states"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OAUTH_TOKENS = sa.table(
    "oauth_tokens",
    sa.column("id", sa.Uuid),
    sa.column("access_token", sa.Text),
    sa.column("refresh_token", sa.Text),
)


def _get_fernet() -> Fernet:
    import os

    key = os.environ.get("OAUTH_ENCRYPTION_KEY", "")
    if not key:
        raise RuntimeError(
            "OAUTH_ENCRYPTION_KEY must be set before running "
            "this migration. Generate with: python -c "
            '"from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def _is_fernet_token(value: str) -> bool:
    """Fernet tokens start with gAAAAA (base64-encoded version byte)."""
    return value.startswith("gAAAAA")


def upgrade() -> None:
    conn = op.get_bind()
    f = _get_fernet()

    rows = conn.execute(sa.select(OAUTH_TOKENS)).fetchall()
    for row in rows:
        updates: dict[str, str] = {}
        if row.access_token and not _is_fernet_token(row.access_token):
            updates["access_token"] = f.encrypt(row.access_token.encode()).decode()
        if row.refresh_token and not _is_fernet_token(row.refresh_token):
            updates["refresh_token"] = f.encrypt(row.refresh_token.encode()).decode()

        if updates:
            conn.execute(
                OAUTH_TOKENS.update()
                .where(OAUTH_TOKENS.c.id == row.id)
                .values(**updates)
            )


def downgrade() -> None:
    conn = op.get_bind()
    f = _get_fernet()

    rows = conn.execute(sa.select(OAUTH_TOKENS)).fetchall()
    for row in rows:
        updates: dict[str, str] = {}
        if row.access_token and _is_fernet_token(row.access_token):
            updates["access_token"] = f.decrypt(row.access_token.encode()).decode()
        if row.refresh_token and _is_fernet_token(row.refresh_token):
            updates["refresh_token"] = f.decrypt(row.refresh_token.encode()).decode()

        if updates:
            conn.execute(
                OAUTH_TOKENS.update()
                .where(OAUTH_TOKENS.c.id == row.id)
                .values(**updates)
            )
