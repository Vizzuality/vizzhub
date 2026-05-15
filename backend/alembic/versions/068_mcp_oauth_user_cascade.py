"""Add ON DELETE CASCADE to MCP OAuth FKs on users.id.

Outstanding auth codes and refresh tokens should be revoked automatically
when the owning user is deleted. Without this, admin user deletion fails
with FK violations when the user has active MCP sessions.
"""

from alembic import op

revision = "068_mcp_oauth_user_cascade"
down_revision = "067_widen_cfr_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # mcp_oauth_codes.user_id → users.id
    op.execute(
        "ALTER TABLE mcp_oauth_codes "
        "DROP CONSTRAINT IF EXISTS mcp_oauth_codes_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE mcp_oauth_codes "
        "ADD CONSTRAINT mcp_oauth_codes_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE"
    )

    # mcp_oauth_refresh_tokens.user_id → users.id
    op.execute(
        "ALTER TABLE mcp_oauth_refresh_tokens "
        "DROP CONSTRAINT IF EXISTS mcp_oauth_refresh_tokens_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE mcp_oauth_refresh_tokens "
        "ADD CONSTRAINT mcp_oauth_refresh_tokens_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE mcp_oauth_codes "
        "DROP CONSTRAINT IF EXISTS mcp_oauth_codes_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE mcp_oauth_codes "
        "ADD CONSTRAINT mcp_oauth_codes_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users (id)"
    )

    op.execute(
        "ALTER TABLE mcp_oauth_refresh_tokens "
        "DROP CONSTRAINT IF EXISTS mcp_oauth_refresh_tokens_user_id_fkey"
    )
    op.execute(
        "ALTER TABLE mcp_oauth_refresh_tokens "
        "ADD CONSTRAINT mcp_oauth_refresh_tokens_user_id_fkey "
        "FOREIGN KEY (user_id) REFERENCES users (id)"
    )
