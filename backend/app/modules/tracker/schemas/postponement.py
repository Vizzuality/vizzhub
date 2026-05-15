"""Postponement request/response schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PostponeRequest(BaseModel):
    postponed_to: date
    reason: str = Field(..., min_length=1, max_length=500)


class PostponementResponse(BaseModel):
    id: UUID
    invoice_id: UUID
    postponed_to: date
    reason: str
    created_by: UUID | None
    created_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
