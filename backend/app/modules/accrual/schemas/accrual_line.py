"""Pydantic schemas for accrual line CRUD + project links."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


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
    def _window_ordered(self) -> "LineCreate":
        if self.window_start and self.window_end and self.window_start > self.window_end:
            raise ValueError("window_start must be on or before window_end")
        return self


class LineUpdate(BaseModel):
    """Partial update. Only fields present in the payload are written
    (``model_fields_set``), so omitting a field leaves it untouched."""

    name: str | None = None
    value_eur: Decimal | None = Field(None, ge=0)
    value_orig: Decimal | None = Field(None, ge=0)
    currency: str | None = None
    window_start: date | None = None
    window_end: date | None = None

    @model_validator(mode="after")
    def _window_ordered(self) -> "LineUpdate":
        if self.window_start and self.window_end and self.window_start > self.window_end:
            raise ValueError("window_start must be on or before window_end")
        return self


class LineProjectLink(BaseModel):
    project_id: UUID
