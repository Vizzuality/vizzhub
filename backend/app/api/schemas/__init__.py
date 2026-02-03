"""Pydantic schemas for API endpoints."""

from app.api.schemas.job import (
    CaptureHistoryRequest,
    JobDetailResponse,
    JobResponse,
    JobSummaryResponse,
)
from app.api.schemas.slack import (
    AlertDefinitionResponse,
    AlertDefinitionUpdate,
    MessageTemplateResponse,
    MessageTemplateUpdate,
    SlackChannel,
    SlackConfigResponse,
    SlackConfigUpdate,
    SlackTestResult,
)

__all__ = [
    "CaptureHistoryRequest",
    "JobDetailResponse",
    "JobResponse",
    "JobSummaryResponse",
    "AlertDefinitionResponse",
    "AlertDefinitionUpdate",
    "MessageTemplateResponse",
    "MessageTemplateUpdate",
    "SlackChannel",
    "SlackConfigResponse",
    "SlackConfigUpdate",
    "SlackTestResult",
]
