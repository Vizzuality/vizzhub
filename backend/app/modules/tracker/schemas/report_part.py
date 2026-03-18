"""Pydantic schemas for report parts."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReportPartCreate(BaseModel):
    report_id: UUID
    project_id: UUID
    functional_area_id: UUID | None = None
    percentage: Decimal = Field(ge=0, le=1)


class ReportPartUpdate(BaseModel):
    functional_area_id: UUID | None = None
    percentage: Decimal | None = Field(default=None, ge=0, le=1)


class ReportPartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    report_id: UUID
    project_id: UUID
    project_name: str | None = None
    functional_area_id: UUID | None
    percentage: float | None
    days: float | None
    cost: float | None
    created_at: datetime
    updated_at: datetime
