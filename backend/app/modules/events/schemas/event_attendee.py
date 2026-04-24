"""Pydantic schemas for event attendees."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.events.constants import AttendeeRole


class AttendeeCreate(BaseModel):
    user_id: UUID
    role: AttendeeRole
    cost: Decimal | None = Field(None, ge=0)


class AttendeeUpdate(BaseModel):
    role: AttendeeRole | None = None
    cost: Decimal | None = Field(None, ge=0)


class AttendeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    user_id: UUID
    role: str
    cost: Decimal | None = None
    user_name: str | None = None
    user_email: str | None = None
    functional_area: str | None = None
    created_at: datetime
