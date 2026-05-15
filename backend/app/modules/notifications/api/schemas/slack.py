"""Slack API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.schemas.common import PaginatedResponse


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
    channel_id: str | None = None
    channel_label: str | None = None


class JobTriggerResponse(BaseModel):
    """Response from manually triggering a scheduled job."""

    success: bool
    message: str
    job_id: str | None = None


class ScheduledJobChannelUpdate(BaseModel):
    """Request to update a scheduled job's Slack channel."""

    channel_id: str = Field(..., min_length=1, max_length=50)


class AlertTestResponse(BaseModel):
    """Response from testing an alert."""

    ok: bool
    message: str
    channel_id: str | None = None
    error: str | None = None


class CustomNotificationRequest(BaseModel):
    """Request to send a custom Slack notification."""

    slack_user_id: str = Field(..., description="Slack user ID to DM")
    message: str = Field(..., min_length=1, description="Message text (Slack mrkdwn)")
    unfurl_links: bool = Field(True, description="Enable link previews")
    unfurl_media: bool = Field(False, description="Enable media (image/video) previews")


class CustomNotificationResponse(BaseModel):
    """Response from sending a custom notification."""

    ok: bool
    message: str
    error: str | None = None
