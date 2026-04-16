"""Pydantic schemas for event attendees."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.events.constants import AttendeeRole


class AttendeeCreate(BaseModel):
    user_id: UUID
    role: AttendeeRole


class AttendeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    user_id: UUID
    role: str
    user_name: str | None = None
    user_email: str | None = None
    functional_area: str | None = None
    created_at: datetime
