"""Pydantic schemas for reports."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReportCreate(BaseModel):
    reporting_period_id: UUID
    estimated: bool = False


class ReportUpdate(BaseModel):
    estimated: bool | None = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    reporting_period_id: UUID
    estimated: bool
    user_name: str | None = None
    user_email: str | None = None
    created_at: datetime
    updated_at: datetime


class ReportWithPartsResponse(ReportResponse):
    parts: list["ReportPartResponse"] = []


from app.modules.tracker.schemas.report_part import ReportPartResponse  # noqa: E402

ReportWithPartsResponse.model_rebuild()
