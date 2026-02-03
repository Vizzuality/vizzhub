"""Slack notification models."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


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
        Integer, ForeignKey("alert_definitions.id", ondelete="CASCADE"), nullable=False
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
