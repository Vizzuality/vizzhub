"""Add composite index ix_jobs_status_created on jobs(status, created_at).

Job listing endpoints filter on status and order by created_at; the existing
single-column indexes don't combine.
"""

from alembic import op

revision = "069_jobs_status_created_idx"
down_revision = "068_mcp_oauth_user_cascade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_status_created "
        "ON jobs (status, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_jobs_status_created")
