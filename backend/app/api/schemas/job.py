"""Pydantic schemas for Job API."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.job import JobStatus, JobType


class CaptureHistoryRequest(BaseModel):
    """Request to create a historical capture job."""

    project_id: uuid.UUID
    from_year: int = Field(ge=2020, le=2100)
    from_month: int = Field(ge=1, le=12)
    to_year: int = Field(ge=2020, le=2100)
    to_month: int = Field(ge=1, le=12)
    force: bool = True


class JobResponse(BaseModel):
    """Basic job response."""

    id: uuid.UUID
    type: JobType
    status: JobStatus
    name: str
    progress: int
    created_at: datetime

    model_config = {"from_attributes": True}


class JobDetailResponse(JobResponse):
    """Detailed job response for polling."""

    description: str | None
    project_id: uuid.UUID | None
    params: dict
    result: dict | None
    progress_message: str | None
    logs: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class JobSummaryResponse(BaseModel):
    """Summary for job listing."""

    id: uuid.UUID
    type: JobType
    status: JobStatus
    name: str
    progress: int
    project_id: uuid.UUID | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
