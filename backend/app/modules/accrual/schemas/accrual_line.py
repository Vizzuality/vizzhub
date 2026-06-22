"""Pydantic schemas for accrual line CRUD + project links."""

from datetime import date
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


def _validate_window_order(start: date | None, end: date | None) -> None:
    if start and end and start > end:
        raise ValueError("window_start must be on or before window_end")


class LineCreate(BaseModel):
    """Create a manual line. ``project_ids`` links it to 0..N projects up front."""

    name: str | None = None
    value_eur: Decimal = Field(Decimal("0"), ge=0)
    value_orig: Decimal | None = Field(None, ge=0)
    currency: str | None = None
    window_start: date | None = None
    window_end: date | None = None
    project_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _window_ordered(self) -> Self:
        _validate_window_order(self.window_start, self.window_end)
        return self


class LineUpdate(BaseModel):
    """Partial update. Only fields present in the payload are written
    (``model_fields_set``), so omitting a field leaves it untouched."""

    name: str | None = None
    value_eur: Decimal | None = Field(None, ge=0)
    value_orig: Decimal | None = Field(None, ge=0)
    currency: str | None = None
    rate: Decimal | None = Field(None, gt=0)
    window_start: date | None = None
    window_end: date | None = None
    include_frozen: bool = False

    @model_validator(mode="after")
    def _window_ordered(self) -> Self:
        _validate_window_order(self.window_start, self.window_end)
        return self


class LineProjectLink(BaseModel):
    project_id: UUID
