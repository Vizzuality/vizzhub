"""Pydantic schemas for AccrualPeriod."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


def _validate_rates(v: dict[str, str]) -> dict[str, str]:
    """Validate fx_rates: ISO-4217 codes, positive Decimal values."""
    for code, rate in v.items():
        if len(code) != 3 or not code.isupper():
            raise ValueError(f"Invalid currency code: {code!r}")
        try:
            d = Decimal(rate)
        except Exception as exc:
            raise ValueError(f"Invalid rate for {code}: {rate!r}") from exc
        if d <= 0:
            raise ValueError(f"Rate for {code} must be > 0")
    return v


class AccrualPeriodBase(BaseModel):
    """Base schema for AccrualPeriod requests."""

    start_date: date
    fx_rates: dict[str, str]

    @field_validator("fx_rates")
    @classmethod
    def _validate_fx_rates(cls, v: dict[str, str]) -> dict[str, str]:
        return _validate_rates(v)


class AccrualPeriodCreate(AccrualPeriodBase):
    """Schema for creating a new AccrualPeriod."""

    pass


class AccrualPeriodUpdate(BaseModel):
    """Schema for updating an existing AccrualPeriod."""

    fx_rates: dict[str, str] | None = None

    @field_validator("fx_rates")
    @classmethod
    def _validate_fx_rates(cls, v: dict[str, str] | None) -> dict[str, str] | None:
        if v is None:
            return None
        return _validate_rates(v)


class AccrualPeriod(AccrualPeriodBase):
    """Response schema for AccrualPeriod (with ORM attributes)."""

    id: UUID
    status: Literal["open", "closed"]
    closed_at: datetime | None
    created_at: datetime
    created_by: UUID | None

    model_config = {"from_attributes": True}
