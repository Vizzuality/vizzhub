"""Migrate project status: in_progress -> live, add proposal state.

Revision ID: 020_status_migration
Revises: 019_tracker_module
Create Date: 2026-03-14

Changes project status enum from (in_progress, finished) to (proposal, live, finished).
Updates existing rows: in_progress -> live.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020_status_migration"
down_revision: Union[str, None] = "019_tracker_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE projects SET status = 'live' WHERE status = 'in_progress'")


def downgrade() -> None:
    op.execute("UPDATE projects SET status = 'in_progress' WHERE status = 'live'")
    op.execute("UPDATE projects SET status = 'in_progress' WHERE status = 'proposal'")
