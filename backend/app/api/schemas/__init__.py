"""Pydantic schemas for API endpoints."""

from app.api.schemas.common import PaginatedResponse
from app.api.schemas.job import (
    CaptureHistoryRequest,
    JobDetailResponse,
    JobResponse,
    JobSummaryResponse,
)
from app.api.schemas.project import (
    PaginatedProjectsResponse,
    ProjectSummary,
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
    "PaginatedResponse",
    "CaptureHistoryRequest",
    "JobDetailResponse",
    "JobResponse",
    "JobSummaryResponse",
    "PaginatedProjectsResponse",
    "ProjectSummary",
    "AlertDefinitionResponse",
    "AlertDefinitionUpdate",
    "MessageTemplateResponse",
    "MessageTemplateUpdate",
    "SlackChannel",
    "SlackConfigResponse",
    "SlackConfigUpdate",
    "SlackTestResult",
]
