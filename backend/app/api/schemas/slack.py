"""Slack API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.api.schemas.common import PaginatedResponse


class SlackConfigResponse(BaseModel):
    """Slack config response (token masked)."""

    id: int
    bot_token_configured: bool
    leadership_channel_id: str | None = None
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
    description: str | None = None
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


class AlertSilenceCreate(BaseModel):
    """Create a new silence."""

    project_id: str = Field(..., description="Project UUID")
    alert_definition_id: int | None = Field(
        None, description="Null = silence all alerts"
    )
    silenced_until: datetime | None = Field(None, description="Null = indefinite")
    reason: str | None = None


class AlertSilenceUpdate(BaseModel):
    """Update a silence."""

    silenced_until: datetime | None = None
    reason: str | None = None


class AlertSilenceResponse(BaseModel):
    """Silence response."""

    id: int
    project_id: str
    alert_definition_id: int | None = None
    silenced_until: datetime | None = None
    reason: str | None = None
    created_by: str | None = None
    created_at: datetime

    project_name: str | None = None
    alert_name: str | None = None

    model_config = {"from_attributes": True}


class AlertNotificationResponse(BaseModel):
    """Notification log entry response."""

    id: int
    project_id: str
    alert_definition_id: int
    channel_id: str
    message: str
    status: str
    error_message: str | None = None
    metadata_json: dict | None = None
    sent_at: datetime

    project_name: str | None = None
    alert_name: str | None = None

    model_config = {"from_attributes": True}


class NotificationStatsResponse(BaseModel):
    """Notification statistics."""

    total_this_month: int
    by_type: dict[str, int]
    by_project: list[dict]
    avg_vulnerability_resolution_days: float | None = None


PaginatedNotificationsResponse = PaginatedResponse[AlertNotificationResponse]


class ScheduledJobLastRun(BaseModel):
    """Last run info for a scheduled job."""

    id: int
    started_at: datetime
    completed_at: datetime | None = None
    status: str
    projects_checked: int
    alerts_sent: int
    error_message: str | None = None

    model_config = {"from_attributes": True}


class ScheduledJobInfo(BaseModel):
    """Scheduled job info with last run status."""

    name: str
    schedule: str
    description: str
    last_run: ScheduledJobLastRun | None = None


class JobTriggerResponse(BaseModel):
    """Response from manually triggering a scheduled job."""

    success: bool
    message: str
    job_id: str | None = None


class AlertTestResponse(BaseModel):
    """Response from testing an alert."""

    ok: bool
    message: str
    channel_id: str | None = None
    error: str | None = None
