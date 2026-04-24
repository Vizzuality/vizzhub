"""Pydantic schemas for events."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.events.constants import EventType, RegionFocus, Theme


class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    event_type: EventType
    theme_primary: Theme
    theme_secondary: Theme | None = None
    region_focus: RegionFocus
    location_city: str | None = Field(None, max_length=100)
    location_country: str | None = Field(None, max_length=100)
    start_date: date
    end_date: date | None = None
    other_costs: Decimal = Field(default=Decimal("0"), ge=0)
    rating: int | None = Field(None, ge=1, le=5)
    url: str | None = Field(None, max_length=500)
    observations: str | None = None


class EventUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=300)
    event_type: EventType | None = None
    theme_primary: Theme | None = None
    theme_secondary: Theme | None = None
    region_focus: RegionFocus | None = None
    location_city: str | None = Field(None, max_length=100)
    location_country: str | None = Field(None, max_length=100)
    start_date: date | None = None
    end_date: date | None = None
    other_costs: Decimal | None = Field(None, ge=0)
    rating: int | None = Field(None, ge=1, le=5)
    url: str | None = Field(None, max_length=500)
    observations: str | None = None


class RsvpCounts(BaseModel):
    going: int = 0
    maybe: int = 0
    not_going: int = 0


class UserSummary(BaseModel):
    id: UUID
    first_name: str | None = None
    last_name: str | None = None
    email: str


class RsvpLists(BaseModel):
    going: list[UserSummary] = []
    maybe: list[UserSummary] = []
    not_going: list[UserSummary] = []


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    event_type: str
    theme_primary: str
    theme_secondary: str | None = None
    region_focus: str
    location_city: str | None = None
    location_country: str | None = None
    start_date: date
    end_date: date | None = None
    other_costs: Decimal
    total_cost: Decimal
    rating: int | None = None
    url: str | None = None
    observations: str | None = None
    created_by: UUID | None = None
    attendee_count: int = 0
    attendee_names: list[str] = []
    created_at: datetime
    updated_at: datetime
    rsvp_counts: RsvpCounts = Field(default_factory=RsvpCounts)
    my_rsvp_status: Literal["going", "maybe", "not_going"] | None = None


class EventWithAttendeesResponse(EventResponse):
    attendees: list["AttendeeResponse"] = []
    rsvps: RsvpLists = Field(default_factory=RsvpLists)


from app.modules.events.schemas.event_attendee import AttendeeResponse  # noqa: E402

EventWithAttendeesResponse.model_rebuild()
