"""Pydantic schemas for reporting periods."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tracker.constants import DEFAULT_RATE


class ReportingPeriodCreate(BaseModel):
    date: dt.date
    base_rate: Decimal = Field(default=DEFAULT_RATE, ge=0)


class ReportingPeriodUpdate(BaseModel):
    date: dt.date | None = None
    base_rate: Decimal | None = Field(default=None, ge=0)


class ReportingPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date: dt.date
    base_rate: float
    status: str
    report_count: int = 0
    created_at: dt.datetime
    updated_at: dt.datetime
