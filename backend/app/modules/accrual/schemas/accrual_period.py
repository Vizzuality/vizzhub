"""Pydantic schemas for AccrualPeriod."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class AccrualPeriodBase(BaseModel):
    """Base schema for AccrualPeriod requests."""

    start_date: date


class AccrualPeriodCreate(AccrualPeriodBase):
    """Schema for creating a new AccrualPeriod."""

    pass


class AccrualPeriodUpdate(BaseModel):
    """Schema for updating an existing AccrualPeriod (currently no editable fields)."""

    pass


class AccrualPeriod(AccrualPeriodBase):
    """Response schema for AccrualPeriod (with ORM attributes)."""

    id: UUID
    status: Literal["open", "closed"]
    closed_at: datetime | None
    created_at: datetime
    created_by: UUID | None

    model_config = {"from_attributes": True}
