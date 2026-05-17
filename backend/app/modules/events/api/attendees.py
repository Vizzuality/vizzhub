"""Event attendee management endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.api.deps import DBSession
from app.modules.events.api.deps import EventsManager, get_event_or_404
from app.modules.events.models.event_attendee import EventAttendeeDB
from app.modules.events.schemas.event_attendee import (
    AttendeeCreate,
    AttendeeResponse,
    AttendeeUpdate,
)
from app.modules.events.services.event_service import load_attendee_details

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/{event_id}/attendees",
    status_code=201,
    responses={
        404: {"description": "Event not found"},
        409: {"description": "Duplicate attendee"},
    },
)
async def add_attendees(
    event_id: UUID,
    body: list[AttendeeCreate],
    db: DBSession,
    user: EventsManager,
) -> list[AttendeeResponse]:
    await get_event_or_404(db, event_id)

    created_ids: list[UUID] = []
    for item in body:
        attendee = EventAttendeeDB(
            event_id=event_id,
            user_id=item.user_id,
            role=item.role,
            cost=item.cost,
        )
        db.add(attendee)
        try:
            await db.flush()
            created_ids.append(attendee.id)
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"User {item.user_id} is already an attendee of this event",
            )

    await db.commit()
    logger.info(
        "attendees_added",
        event_id=str(event_id),
        count=len(created_ids),
    )
    details = await load_attendee_details(db, [event_id], attendee_ids=created_ids)
    return [AttendeeResponse(**d) for d in details]


@router.delete(
    "/{event_id}/attendees/{user_id}",
    status_code=204,
    responses={404: {"description": "Attendee not found"}},
)
async def remove_attendee(
    event_id: UUID,
    user_id: UUID,
    db: DBSession,
    user: EventsManager,
) -> None:
    result = await db.execute(
        select(EventAttendeeDB).where(
            EventAttendeeDB.event_id == event_id,
            EventAttendeeDB.user_id == user_id,
        )
    )
    attendee = result.scalar_one_or_none()
    if attendee is None:
        raise HTTPException(status_code=404, detail="Attendee not found")

    await db.delete(attendee)
    await db.commit()
    logger.info(
        "attendee_removed",
        event_id=str(event_id),
        user_id=str(user_id),
    )


@router.patch(
    "/{event_id}/attendees/{user_id}",
    responses={
        400: {"description": "Invalid cost"},
        404: {"description": "Event or attendee not found"},
    },
)
async def update_attendee(
    event_id: UUID,
    user_id: UUID,
    body: AttendeeUpdate,
    db: DBSession,
    user: EventsManager,
) -> AttendeeResponse:
    await get_event_or_404(db, event_id)
    result = await db.execute(
        select(EventAttendeeDB).where(
            EventAttendeeDB.event_id == event_id,
            EventAttendeeDB.user_id == user_id,
        )
    )
    attendee = result.scalar_one_or_none()
    if attendee is None:
        raise HTTPException(status_code=404, detail="Attendee not found")

    updates = body.model_dump(exclude_unset=True)
    if "role" in updates:
        attendee.role = updates["role"]
    if "cost" in updates:
        attendee.cost = updates["cost"]

    await db.commit()
    logger.info(
        "attendee_updated",
        event_id=str(event_id),
        user_id=str(user_id),
        fields=list(updates.keys()),
    )
    details = await load_attendee_details(db, [event_id], attendee_ids=[attendee.id])
    return AttendeeResponse(**details[0])
