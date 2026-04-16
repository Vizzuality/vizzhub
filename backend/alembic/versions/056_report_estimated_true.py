"""Default estimated to true for new reports.

New reports should be unconfirmed (estimated=true) until the user
explicitly confirms them.

Revision ID: 056_est_true
Revises: 055_create_events
"""

from alembic import op

revision = "056_est_true"
down_revision = "055_create_events"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE reports "
        "ALTER COLUMN estimated SET DEFAULT true"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE reports "
        "ALTER COLUMN estimated SET DEFAULT false"
    )
