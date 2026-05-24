"""Pydantic schemas for AccrualDriftFinding."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DriftFinding(BaseModel):
    id: UUID
    kind: str
    project_id: UUID | None
    project_name: str | None = None
    project_code: str | None = None
    excel_code: str | None
    detected_at: datetime
    resolved_at: datetime | None
    resolution: str | None
    resolved_by: UUID | None
    payload: dict[str, Any] = Field(default_factory=dict)
    import_run_id: UUID | None

    model_config = {"from_attributes": True}


class DriftFindingsResponse(BaseModel):
    items: list[DriftFinding]
    total: int


class DriftResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=1, max_length=1000)


class DriftSummaryBucket(BaseModel):
    open: int = 0
    resolved: int = 0


class DriftSummaryResponse(BaseModel):
    by_kind: dict[str, DriftSummaryBucket]
    total_open: int
    total_resolved: int
