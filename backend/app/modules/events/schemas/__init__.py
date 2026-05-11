"""Event module Pydantic schemas."""

from app.modules.events.schemas.event import (
    Attending,
    EventCreate,
    EventResponse,
    EventUpdate,
    EventWithAttendeesResponse,
)
from app.modules.events.schemas.event_attendee import (
    AttendeeCreate,
    AttendeeResponse,
    AttendeeUpdate,
)

__all__ = [
    "AttendeeCreate",
    "AttendeeResponse",
    "AttendeeUpdate",
    "Attending",
    "EventCreate",
    "EventResponse",
    "EventUpdate",
    "EventWithAttendeesResponse",
]
