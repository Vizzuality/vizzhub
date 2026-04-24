"""Events: split cost into other_costs + per-attendee cost; add RSVP table.

Revision ID: 065_events_cost_rsvp
Revises: 064_drop_devstack_ctx
Create Date: 2026-04-24
"""

from alembic import op


revision = "065_events_cost_rsvp"
down_revision = "064_drop_devstack_ctx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add events.other_costs with default 0
    op.execute(
        "ALTER TABLE events "
        "ADD COLUMN other_costs NUMERIC(12, 2) NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE events "
        "ADD CONSTRAINT ck_events_other_costs_positive "
        "CHECK (other_costs >= 0)"
    )

    # 2. Backfill from the old cost column
    op.execute("UPDATE events SET other_costs = cost")

    # 3. Drop old cost column and its check
    op.execute(
        "ALTER TABLE events DROP CONSTRAINT IF EXISTS ck_events_cost_positive"
    )
    op.execute("ALTER TABLE events DROP COLUMN cost")

    # 4. Add event_attendees.cost (nullable)
    op.execute(
        "ALTER TABLE event_attendees "
        "ADD COLUMN cost NUMERIC(12, 2) NULL"
    )
    op.execute(
        "ALTER TABLE event_attendees "
        "ADD CONSTRAINT ck_event_attendees_cost_positive "
        "CHECK (cost IS NULL OR cost >= 0)"
    )

    # 5. Create event_rsvps table
    op.execute(
        "CREATE TABLE event_rsvps ("
        "id UUID PRIMARY KEY DEFAULT gen_random_uuid(),"
        "event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,"
        "user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
        "status VARCHAR(20) NOT NULL,"
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),"
        "CONSTRAINT ck_event_rsvps_status "
        "CHECK (status IN ('going','maybe','not_going')),"
        "CONSTRAINT uq_event_rsvps_event_user UNIQUE (event_id, user_id)"
        ")"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_event_rsvps_event_id "
        "ON event_rsvps (event_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS event_rsvps")
    op.execute(
        "ALTER TABLE event_attendees "
        "DROP CONSTRAINT IF EXISTS ck_event_attendees_cost_positive"
    )
    op.execute("ALTER TABLE event_attendees DROP COLUMN IF EXISTS cost")
    op.execute(
        "ALTER TABLE events ADD COLUMN cost NUMERIC(12, 2) NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE events "
        "ADD CONSTRAINT ck_events_cost_positive CHECK (cost >= 0)"
    )
    op.execute("UPDATE events SET cost = other_costs")
    op.execute(
        "ALTER TABLE events "
        "DROP CONSTRAINT IF EXISTS ck_events_other_costs_positive"
    )
    op.execute("ALTER TABLE events DROP COLUMN IF EXISTS other_costs")
