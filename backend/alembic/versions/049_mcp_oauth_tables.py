"""Add MCP OAuth tables for dynamic client registration, auth codes, and refresh tokens.

Revision ID: 049_mcp_oauth
Revises: 048_fts_search_vector
"""

from alembic import op

revision = "049_mcp_oauth"
down_revision = "048_fts_search_vector"


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS mcp_oauth_clients ("
        "    client_id       VARCHAR(128) PRIMARY KEY,"
        "    client_secret   VARCHAR(256),"
        "    client_info     JSONB NOT NULL,"
        "    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "    expires_at      TIMESTAMPTZ"
        ")"
    )

    op.execute(
        "CREATE TABLE IF NOT EXISTS mcp_oauth_codes ("
        "    code            VARCHAR(256) PRIMARY KEY,"
        "    client_id       VARCHAR(128) NOT NULL"
        "        REFERENCES mcp_oauth_clients(client_id) ON DELETE CASCADE,"
        "    code_challenge  VARCHAR(256) NOT NULL,"
        "    redirect_uri    TEXT NOT NULL,"
        "    redirect_uri_provided_explicitly BOOLEAN NOT NULL DEFAULT false,"
        "    scopes          JSONB,"
        "    user_id         UUID REFERENCES users(id),"
        "    user_email      VARCHAR(255),"
        "    user_roles      JSONB,"
        "    user_permissions JSONB,"
        "    resource        TEXT,"
        "    expires_at      TIMESTAMPTZ NOT NULL,"
        "    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )

    op.execute(
        "CREATE TABLE IF NOT EXISTS mcp_oauth_refresh_tokens ("
        "    token           VARCHAR(256) PRIMARY KEY,"
        "    client_id       VARCHAR(128) NOT NULL"
        "        REFERENCES mcp_oauth_clients(client_id) ON DELETE CASCADE,"
        "    user_id         UUID REFERENCES users(id),"
        "    user_email      VARCHAR(255),"
        "    user_roles      JSONB,"
        "    user_permissions JSONB,"
        "    scopes          JSONB,"
        "    resource        TEXT,"
        "    expires_at      TIMESTAMPTZ NOT NULL,"
        "    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mcp_oauth_codes_expires "
        "ON mcp_oauth_codes(expires_at)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_mcp_oauth_refresh_tokens_expires "
        "ON mcp_oauth_refresh_tokens(expires_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_mcp_oauth_refresh_tokens_expires")
    op.execute("DROP INDEX IF EXISTS ix_mcp_oauth_codes_expires")
    op.execute("DROP TABLE IF EXISTS mcp_oauth_refresh_tokens")
    op.execute("DROP TABLE IF EXISTS mcp_oauth_codes")
    op.execute("DROP TABLE IF EXISTS mcp_oauth_clients")
