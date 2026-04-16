"""Create events and event_attendees tables.

Revision ID: 055_create_events
Revises: 054_planner_cmt
"""

from alembic import op

revision = "055_create_events"
down_revision = "054_planner_cmt"


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(300) NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            theme_primary VARCHAR(100) NOT NULL,
            theme_secondary VARCHAR(100),
            region_focus VARCHAR(50) NOT NULL,
            location_city VARCHAR(100),
            location_country VARCHAR(100),
            start_date DATE NOT NULL,
            end_date DATE,
            cost NUMERIC(12, 2) NOT NULL DEFAULT 0,
            rating SMALLINT,
            url VARCHAR(500),
            observations TEXT,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT ck_events_rating_range CHECK (rating >= 1 AND rating <= 5),
            CONSTRAINT ck_events_cost_positive CHECK (cost >= 0)
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_events_start_date ON events (start_date)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS event_attendees (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            role VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_event_attendees_event_user UNIQUE (event_id, user_id)
        )
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_event_attendees_event_id"
        " ON event_attendees (event_id)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_event_attendees_user_id"
        " ON event_attendees (user_id)"
    )

    op.execute(
        "INSERT INTO roles (id, name)"
        " VALUES (gen_random_uuid(), 'events_manager')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE name = 'events_manager'")

    op.execute("DROP TABLE IF EXISTS event_attendees")

    op.execute("DROP TABLE IF EXISTS events")
