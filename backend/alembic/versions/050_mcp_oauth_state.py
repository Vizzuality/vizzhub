"""Add mcp_state column to mcp_oauth_codes for MCP client state passthrough.

Revision ID: 050_mcp_state
Revises: 049_mcp_oauth
"""

from alembic import op

revision = "050_mcp_state"
down_revision = "049_mcp_oauth"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE mcp_oauth_codes "
        "ADD COLUMN IF NOT EXISTS mcp_state TEXT"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE mcp_oauth_codes "
        "DROP COLUMN IF EXISTS mcp_state"
    )
