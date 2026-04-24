"""Pydantic schemas for event RSVPs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


RsvpStatus = Literal["going", "maybe", "not_going"]


class RsvpSet(BaseModel):
    status: RsvpStatus


class RsvpResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    user_id: UUID
    status: RsvpStatus
    updated_at: datetime
