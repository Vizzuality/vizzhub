"""Store MCP refresh tokens as SHA-256 hashes.

Read access to mcp_oauth_refresh_tokens used to yield tokens that could be
exchanged for an access token as their user. The column now holds the hex
SHA-256 of the token; the provider hashes the presented token to look it up.
Existing rows are hashed in place, so connected clients keep their sessions.
Downgrade cannot recover the tokens: it deletes them, and clients log in again.

Revision ID: 103_hash_mcp_refresh_tokens
Revises: 102_drop_non_billable_lines
"""

from alembic import op

revision = "103_hash_mcp_refresh_tokens"
down_revision = "102_drop_non_billable_lines"


def upgrade() -> None:
    op.execute("ALTER TABLE mcp_oauth_refresh_tokens RENAME COLUMN token TO token_hash")
    op.execute(
        "UPDATE mcp_oauth_refresh_tokens "
        "SET token_hash = encode(sha256(convert_to(token_hash, 'UTF8')), 'hex')"
    )
    op.execute("ALTER TABLE mcp_oauth_refresh_tokens ALTER COLUMN token_hash TYPE varchar(64)")


def downgrade() -> None:
    op.execute("DELETE FROM mcp_oauth_refresh_tokens")
    op.execute("ALTER TABLE mcp_oauth_refresh_tokens ALTER COLUMN token_hash TYPE varchar(256)")
    op.execute("ALTER TABLE mcp_oauth_refresh_tokens RENAME COLUMN token_hash TO token")
