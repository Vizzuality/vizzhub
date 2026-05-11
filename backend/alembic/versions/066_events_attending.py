"""Add events.attending column, roll up event_rsvps, drop table.

Revision ID: 066_events_attending
Revises: 065_events_cost_rsvp
Create Date: 2026-05-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "066_events_attending"
down_revision = "065_events_cost_rsvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("attending", sa.String(length=10), nullable=True),
    )
    op.create_check_constraint(
        "ck_events_attending",
        "events",
        "attending IN ('yes','no','maybe')",
    )

    op.execute(
        """
        UPDATE events e SET attending = sub.value
        FROM (
            SELECT event_id,
                CASE
                    WHEN bool_or(status = 'going') THEN 'yes'
                    WHEN bool_and(status = 'not_going') THEN 'no'
                    ELSE 'maybe'
                END AS value
            FROM event_rsvps
            GROUP BY event_id
        ) sub
        WHERE e.id = sub.event_id;
        """
    )

    op.drop_table("event_rsvps")


def downgrade() -> None:
    op.create_table(
        "event_rsvps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('going','maybe','not_going')",
            name="ck_event_rsvps_status",
        ),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_rsvps_event_user"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_event_rsvps_event_id", "event_rsvps", ["event_id"])

    op.drop_constraint("ck_events_attending", "events", type_="check")
    op.drop_column("events", "attending")
