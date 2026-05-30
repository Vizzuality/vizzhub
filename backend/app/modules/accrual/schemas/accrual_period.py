"""Pydantic schemas for AccrualPeriod."""

from datetime import date, datetime
from decimal import Decimal
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
    """Response schema for AccrualPeriod (with ORM attributes).

    ``usd_rate`` is the ECB USD/EUR rate effective at ``start_date`` (units of
    USD per 1 EUR). Not stored — looked up on read from ``exchange_rates``.

    ``fx_rates`` is the per-currency rate the CEO actually used that period
    (stored, e.g. ``{"USD": "1.08", "GBP": "0.85"}`` — units of foreign per 1
    EUR). Authoritative audit trail; the ECB ``usd_rate`` is reference only.
    """

    id: UUID
    status: Literal["open", "closed"]
    closed_at: datetime | None
    created_at: datetime
    created_by: UUID | None
    usd_rate: Decimal | None = None
    fx_rates: dict[str, str] = {}

    model_config = {"from_attributes": True}
