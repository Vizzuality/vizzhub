"""Widen metrics.change_failure_rate from NUMERIC(5,4) to NUMERIC(5,2).

The collector emits CFR as a percentage 0-100 (e.g. 41.7) and the DORA
classifier interprets it as a percentage (thresholds 5/10/15). The original
NUMERIC(5,4) column only fits absolute values < 10, so any project with
CFR ≥ 10% causes an INSERT to fail with NumericValueOutOfRangeError. This
went unnoticed until a project genuinely had hotfix releases.

Revision ID: 067_widen_cfr_column
Revises: 066_events_attending
Create Date: 2026-05-14
"""

from alembic import op

revision = "067_widen_cfr_column"
down_revision = "066_events_attending"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE metrics ALTER COLUMN change_failure_rate TYPE NUMERIC(5, 2)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE metrics ALTER COLUMN change_failure_rate TYPE NUMERIC(5, 4) "
        "USING LEAST(change_failure_rate, 9.9999)"
    )
