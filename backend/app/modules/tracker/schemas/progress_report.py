"""Pydantic schemas for progress reports."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProgressReportCreate(BaseModel):
    reporting_period_id: UUID
    percentage: float = Field(ge=0, le=100)


class ProgressReportUpdate(BaseModel):
    percentage: float = Field(ge=0, le=100)


class ProgressReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reporting_period_id: UUID
    project_id: UUID
    period_date: str | None = None
    percentage: float
    delta: float | None


class ProgressSummary(BaseModel):
    """Latest progress for a project (used in batch endpoint)."""

    project_id: UUID
    percentage: float
    delta: float | None


class BatchProgressResponse(BaseModel):
    progress: dict[str, ProgressSummary]
