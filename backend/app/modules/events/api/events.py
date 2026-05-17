"""Events CRUD endpoints."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.core.api.deps import DBSession
from app.modules.events.api.deps import EventsManager, EventsViewer, get_event_or_404
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB
from app.modules.events.schemas.event import (
    EventCreate,
    EventResponse,
    EventUpdate,
    EventWithAttendeesResponse,
)
from app.modules.events.services.event_service import (
    event_to_dict,
    get_event_with_attendees,
    list_events,
)

logger = structlog.get_logger()

router = APIRouter()


def _event_to_response(event: EventDB, attendee_count: int = 0) -> EventResponse:
    return EventResponse(
        **event_to_dict(event),
        attendee_count=attendee_count,
        attendee_names=[],
        total_cost=event.other_costs,
    )


@dataclass
class EventListFilters:
    search: str | None = None
    year: int | None = None
    quarter: Annotated[int | None, Query(ge=1, le=4)] = None
    event_type: str | None = None
    theme_primary: str | None = None
    region_focus: str | None = None
    location_country: str | None = None
    attending: Annotated[str | None, Query(pattern=r"^(yes|no|maybe)$")] = None


@dataclass
class EventListSort:
    sort_by: Annotated[
        str | None,
        Query(pattern=r"^(start_date|total_cost|rating|name)$"),
    ] = None
    sort_dir: Annotated[str | None, Query(pattern=r"^(asc|desc)$")] = None


@router.get("")
async def list_events_endpoint(
    db: DBSession,
    user: EventsViewer,
    f: Annotated[EventListFilters, Depends()],
    s: Annotated[EventListSort, Depends()],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict:
    offset = (page - 1) * page_size
    items, total = await list_events(
        db,
        search=f.search,
        year=f.year,
        quarter=f.quarter,
        event_type=f.event_type,
        theme_primary=f.theme_primary,
        region_focus=f.region_focus,
        location_country=f.location_country,
        attending=f.attending,
        sort_by=s.sort_by,
        sort_dir=s.sort_dir,
        offset=offset,
        limit=page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/{event_id}",
    responses={404: {"description": "Event not found"}},
)
async def get_event(
    event_id: UUID,
    db: DBSession,
    user: EventsViewer,
) -> EventWithAttendeesResponse:
    result = await get_event_with_attendees(event_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventWithAttendeesResponse(**result)


@router.post("", status_code=201)
async def create_event(
    body: EventCreate,
    db: DBSession,
    user: EventsManager,
) -> EventResponse:
    event = EventDB(**body.model_dump(), created_by=user.user_id)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    logger.info(
        "event_created",
        event_id=str(event.id),
        name=event.name,
        other_costs=str(event.other_costs) if event.other_costs is not None else None,
        user_id=user.user_id,
    )
    return _event_to_response(event, attendee_count=0)


@router.put(
    "/{event_id}",
    responses={404: {"description": "Event not found"}},
)
async def update_event(
    event_id: UUID,
    body: EventUpdate,
    db: DBSession,
    user: EventsManager,
) -> EventResponse:
    event = await get_event_or_404(db, event_id)

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)

    count_result = await db.execute(
        select(func.count(EventAttendeeDB.id)).where(EventAttendeeDB.event_id == event_id)
    )
    attendee_count = count_result.scalar() or 0

    logger.info(
        "event_updated",
        event_id=str(event.id),
        fields=sorted(updates.keys()),
        other_costs=str(event.other_costs) if event.other_costs is not None else None,
        attendee_count=attendee_count,
        user_id=user.user_id,
    )

    return _event_to_response(event, attendee_count=attendee_count)


@router.delete(
    "/{event_id}",
    status_code=204,
    responses={404: {"description": "Event not found"}},
)
async def delete_event(
    event_id: UUID,
    db: DBSession,
    user: EventsManager,
) -> None:
    event = await get_event_or_404(db, event_id)

    other_costs = str(event.other_costs) if event.other_costs is not None else None
    await db.delete(event)
    await db.commit()
    logger.info(
        "event_deleted",
        event_id=str(event_id),
        name=event.name,
        other_costs=other_costs,
        user_id=user.user_id,
    )
