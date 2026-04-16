"""Event attendee management endpoints."""

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.user import UserDB
from app.core.permissions import Action, require_permission
from app.core.sql_helpers import user_display_name_expr
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB
from app.modules.events.schemas.event_attendee import AttendeeCreate, AttendeeResponse

logger = structlog.get_logger()

router = APIRouter()

EventsManager = Annotated[TokenData, Depends(require_permission(Action.EVENTS_MANAGE))]


async def _get_event_or_404(db, event_id: UUID) -> EventDB:
    result = await db.execute(select(EventDB).where(EventDB.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


async def _load_attendee_responses(
    db,
    event_id: UUID,
    attendee_ids: list[UUID],
) -> list[AttendeeResponse]:
    user_alias = aliased(UserDB)
    fa_alias = aliased(FunctionalAreaDB)

    stmt = (
        select(
            EventAttendeeDB,
            user_display_name_expr(user_alias).label("user_name"),
            user_alias.email.label("user_email"),
            fa_alias.name.label("functional_area"),
        )
        .join(user_alias, user_alias.id == EventAttendeeDB.user_id)
        .outerjoin(fa_alias, fa_alias.id == user_alias.functional_area_id)
        .where(
            EventAttendeeDB.event_id == event_id,
            EventAttendeeDB.id.in_(attendee_ids),
        )
        .order_by(EventAttendeeDB.role, user_display_name_expr(user_alias))
    )
    result = await db.execute(stmt)
    return [
        AttendeeResponse(
            id=att.id,
            event_id=att.event_id,
            user_id=att.user_id,
            role=att.role,
            user_name=user_name,
            user_email=user_email,
            functional_area=functional_area,
            created_at=att.created_at,
        )
        for att, user_name, user_email, functional_area in result.all()
    ]


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
    await _get_event_or_404(db, event_id)

    created_ids: list[UUID] = []
    for item in body:
        attendee = EventAttendeeDB(
            event_id=event_id,
            user_id=item.user_id,
            role=item.role,
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
    return await _load_attendee_responses(db, event_id, created_ids)


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
