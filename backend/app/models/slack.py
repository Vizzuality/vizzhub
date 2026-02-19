"""Slack notification models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base

FK_ALERT_DEFINITIONS_ID = "alert_definitions.id"
FK_PROJECTS_ID = "projects.id"


class AlertCategory(str, Enum):
    """Category of alerts."""

    BUSINESS = "business"
    PROJECT = "project"


class ChannelType(str, Enum):
    """Target channel type for alerts."""

    LEADERSHIP = "leadership"
    PROJECT = "project"


class AlertSchedule(str, Enum):
    """Schedule type for alert checks."""

    DAILY_CHECK_MONTHLY_REPORT = "daily_check_monthly_report"
    DAILY = "daily"


class TemplateType(str, Enum):
    """Type of message template."""

    INITIAL = "initial"
    REMINDER = "reminder"
    ESCALATION = "escalation"


class SlackConfigDB(Base):
    """Global Slack configuration (single row)."""

    __tablename__ = "slack_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bot_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    leadership_channel_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )


class AlertDefinitionDB(Base):
    """Predefined alert types."""

    __tablename__ = "alert_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(50), nullable=False)
    schedule: Mapped[str] = mapped_column(String(50), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )


class MessageTemplateDB(Base):
    """Customizable message templates."""

    __tablename__ = "message_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_ALERT_DEFINITIONS_ID, ondelete="CASCADE"), nullable=False
    )
    template_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )


class AlertSilenceDB(Base):
    """Per-project alert muting."""

    __tablename__ = "alert_silences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(FK_PROJECTS_ID, ondelete="CASCADE"),
        nullable=False,
    )
    alert_definition_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey(FK_ALERT_DEFINITIONS_ID, ondelete="CASCADE"), nullable=True
    )
    silenced_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AlertNotificationDB(Base):
    """Log of sent alerts."""

    __tablename__ = "alert_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(FK_PROJECTS_ID, ondelete="CASCADE"),
        nullable=False,
    )
    alert_definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey(FK_ALERT_DEFINITIONS_ID, ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DependabotAlertTrackedDB(Base):
    """Track notified Dependabot alerts for deduplication."""

    __tablename__ = "dependabot_alerts_tracked"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(FK_PROJECTS_ID, ondelete="CASCADE"),
        nullable=False,
    )
    github_alert_id: Mapped[int] = mapped_column(Integer, nullable=False)
    package_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cve_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manifest_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ScheduledJobRunDB(Base):
    """Track scheduled job executions."""

    __tablename__ = "scheduled_job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    projects_checked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    alerts_sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
