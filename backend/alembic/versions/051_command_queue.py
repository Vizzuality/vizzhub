"""Add command_queue table for MCP write operations.

Revision ID: 051_cmd_queue
Revises: 050_mcp_state
"""

from alembic import op

revision = "051_cmd_queue"
down_revision = "050_mcp_state"


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS command_queue ("
        "  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "  module TEXT NOT NULL,"
        "  action TEXT NOT NULL,"
        "  target TEXT,"
        "  payload JSONB NOT NULL DEFAULT '{}'::jsonb,"
        "  summary TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  requested_by UUID NOT NULL REFERENCES users(id),"
        "  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "  reviewed_by UUID REFERENCES users(id),"
        "  reviewed_at TIMESTAMPTZ,"
        "  result JSONB,"
        "  error TEXT,"
        "  executed_at TIMESTAMPTZ"
        ")"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_command_queue_status "
        "ON command_queue(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_command_queue_requested_by "
        "ON command_queue(requested_by)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_command_queue_module "
        "ON command_queue(module)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS command_queue")
