"""Add Slack notifications tables

Revision ID: 011_add_slack_notifications
Revises: 010_add_global_metrics_table
Create Date: 2026-02-03

This migration adds all tables required for Slack notifications:
- slack_config: Global Slack configuration (bot token, leadership channel)
- alert_definitions: Predefined alert types with schedules
- message_templates: Customizable message templates per alert
- alert_silences: Per-project alert muting
- alert_notifications: Log of sent alerts
- dependabot_alerts_tracked: Track notified Dependabot alerts
- scheduled_job_runs: Track scheduled job executions

Also adds slack_channel_id to projects table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "011_add_slack_notifications"
down_revision: str | None = "010_add_global_metrics_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FK_ALERT_DEFINITIONS_ID = "alert_definitions.id"
FK_PROJECTS_ID = "projects.id"


def upgrade() -> None:
    # Add slack_channel_id to projects
    op.add_column("projects", sa.Column("slack_channel_id", sa.String(50), nullable=True))

    # slack_config table
    op.create_table(
        "slack_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bot_token_encrypted", sa.Text(), nullable=True),
        sa.Column("leadership_channel_id", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # alert_definitions table
    op.create_table(
        "alert_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("channel_type", sa.String(50), nullable=False),
        sa.Column("schedule", sa.String(50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # message_templates table
    op.create_table(
        "message_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "alert_definition_id",
            sa.Integer(),
            sa.ForeignKey(FK_ALERT_DEFINITIONS_ID, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_type", sa.String(50), nullable=False),
        sa.Column("message_template", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # alert_silences table
    op.create_table(
        "alert_silences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey(FK_PROJECTS_ID, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "alert_definition_id",
            sa.Integer(),
            sa.ForeignKey(FK_ALERT_DEFINITIONS_ID, ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("silenced_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_silences_project_id", "alert_silences", ["project_id"])

    # alert_notifications table
    op.create_table(
        "alert_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey(FK_PROJECTS_ID, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "alert_definition_id",
            sa.Integer(),
            sa.ForeignKey(FK_ALERT_DEFINITIONS_ID, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel_id", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_notifications_project_id", "alert_notifications", ["project_id"])
    op.create_index("ix_alert_notifications_sent_at", "alert_notifications", ["sent_at"])

    # dependabot_alerts_tracked table
    op.create_table(
        "dependabot_alerts_tracked",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey(FK_PROJECTS_ID, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("github_alert_id", sa.Integer(), nullable=False),
        sa.Column("package_name", sa.String(200), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("cve_id", sa.String(50), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "github_alert_id", name="uq_dependabot_project_alert"),
    )
    op.create_index("ix_dependabot_alerts_project_id", "dependabot_alerts_tracked", ["project_id"])

    # scheduled_job_runs table
    op.create_table(
        "scheduled_job_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("projects_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerts_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_scheduled_job_runs_job_name", "scheduled_job_runs", ["job_name"])
    op.create_index("ix_scheduled_job_runs_started_at", "scheduled_job_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_job_runs_started_at", table_name="scheduled_job_runs")
    op.drop_index("ix_scheduled_job_runs_job_name", table_name="scheduled_job_runs")
    op.drop_table("scheduled_job_runs")

    op.drop_index("ix_dependabot_alerts_project_id", table_name="dependabot_alerts_tracked")
    op.drop_table("dependabot_alerts_tracked")

    op.drop_index("ix_alert_notifications_sent_at", table_name="alert_notifications")
    op.drop_index("ix_alert_notifications_project_id", table_name="alert_notifications")
    op.drop_table("alert_notifications")

    op.drop_index("ix_alert_silences_project_id", table_name="alert_silences")
    op.drop_table("alert_silences")

    op.drop_table("message_templates")
    op.drop_table("alert_definitions")
    op.drop_table("slack_config")

    op.drop_column("projects", "slack_channel_id")
