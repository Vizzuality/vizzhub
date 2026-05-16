"""Add devstack_entries.last_fetch_ok_at for stale detection.

Audit Major #8 (2026-05-16): we previously had no honest "freshness"
signal for devstack catalog entries. `updated_at` only advances when a
column actually changes, so a github repo that's been down for a week
looks identical to one that was just refreshed but had no new SHA. This
column records the last time a refresh round actually succeeded for the
entry; callers compute `stale = now - last_fetch_ok_at > 24h` (or
`stale = true` when null and the entry was created more than 24h ago).
"""

from alembic import op

revision = "073_devstack_last_fetch_ok_at"
down_revision = "072_cv_pct_replaces_bv"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries "
        "ADD COLUMN IF NOT EXISTS last_fetch_ok_at TIMESTAMP WITH TIME ZONE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE devstack_entries DROP COLUMN IF EXISTS last_fetch_ok_at"
    )
