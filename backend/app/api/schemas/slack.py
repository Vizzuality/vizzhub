"""Slack API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class SlackConfigResponse(BaseModel):
    """Slack config response (token masked)."""

    id: int
    bot_token_configured: bool
    leadership_channel_id: str | None
    created_at: datetime
    updated_at: datetime


class SlackConfigUpdate(BaseModel):
    """Update Slack config."""

    bot_token: str | None = Field(None, description="Slack bot token (xoxb-...)")
    leadership_channel_id: str | None = Field(None, max_length=50)


class SlackChannel(BaseModel):
    """Slack channel info."""

    id: str
    name: str
    is_private: bool


class SlackTestResult(BaseModel):
    """Result of Slack connection test."""

    ok: bool
    team: str | None = None
    bot_id: str | None = None
    error: str | None = None


class AlertDefinitionResponse(BaseModel):
    """Alert definition response."""

    id: int
    name: str
    description: str | None
    category: str
    channel_type: str
    schedule: str
    is_enabled: bool
    config_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertDefinitionUpdate(BaseModel):
    """Update alert definition."""

    is_enabled: bool | None = None
    config_json: dict | None = None


class MessageTemplateResponse(BaseModel):
    """Message template response."""

    id: int
    alert_definition_id: int
    template_type: str
    message_template: str
    is_active: bool

    model_config = {"from_attributes": True}


class MessageTemplateUpdate(BaseModel):
    """Update message template."""

    message_template: str | None = None
    is_active: bool | None = None
