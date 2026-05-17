"""Pydantic schemas for reporting periods."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.tracker.constants import DEFAULT_RATE


class ReportingPeriodCreate(BaseModel):
    date: dt.date
    base_rate: Decimal = Field(default=DEFAULT_RATE, gt=0)

    @field_validator("date")
    @classmethod
    def normalize_to_first_of_month(cls, v: dt.date) -> dt.date:
        return v.replace(day=1)


class ReportingPeriodUpdate(BaseModel):
    date: dt.date | None = None
    base_rate: Decimal | None = Field(default=None, gt=0)

    @field_validator("date")
    @classmethod
    def normalize_to_first_of_month(cls, v: dt.date | None) -> dt.date | None:
        if v is None:
            return v
        return v.replace(day=1)


class ReportingPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date: dt.date
    base_rate: float
    status: str
    report_count: int = 0
    created_at: dt.datetime
    updated_at: dt.datetime
