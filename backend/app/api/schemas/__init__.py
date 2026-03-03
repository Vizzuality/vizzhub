"""Pydantic schemas for API endpoints.

Re-exports from new module locations for backward compatibility.
"""

from app.modules.scorecard.api.schemas.common import PaginatedResponse
from app.modules.scorecard.api.schemas.job import (
    CaptureHistoryRequest,
    JobDetailResponse,
    JobResponse,
    JobSummaryResponse,
)
from app.modules.scorecard.api.schemas.project import (
    PaginatedProjectsResponse,
    ProjectSummary,
)
from app.modules.scorecard.api.schemas.slack import (
    AlertDefinitionResponse,
    AlertDefinitionUpdate,
    MessageTemplateResponse,
    MessageTemplateUpdate,
    SlackChannel,
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
    "SlackTestResult",
]
