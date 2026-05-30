"""Pydantic schemas for AccrualPeriod."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


def _validated_fx_rates(value: dict[str, str]) -> dict[str, str]:
    """Per-currency CEO rate: ISO-3 uppercase keys, positive decimal values."""
    for code, rate in value.items():
        if not (len(code) == 3 and code.isalpha() and code.isupper()):
            raise ValueError(f"Currency code must be 3 uppercase letters: {code!r}")
        try:
            if Decimal(rate) <= 0:
                raise ValueError
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"Rate for {code} must be a positive number: {rate!r}") from exc
    return value


class AccrualPeriodBase(BaseModel):
    """Base schema for AccrualPeriod requests."""

    start_date: date


class AccrualPeriodCreate(AccrualPeriodBase):
    """Schema for creating a new AccrualPeriod, optionally with the CEO's rates."""

    fx_rates: dict[str, str] = {}

    @field_validator("fx_rates")
    @classmethod
    def _check_fx_rates(cls, v: dict[str, str]) -> dict[str, str]:
        return _validated_fx_rates(v)


class AccrualPeriodUpdate(BaseModel):
    """Schema for updating a period — currently only its CEO fx_rates."""

    fx_rates: dict[str, str]

    @field_validator("fx_rates")
    @classmethod
    def _check_fx_rates(cls, v: dict[str, str]) -> dict[str, str]:
        return _validated_fx_rates(v)


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
