"""Event RSVP endpoints (self-service)."""

from uuid import UUID

import structlog
from fastapi import APIRouter

from app.core.api.deps import CurrentUser, DBSession
from app.modules.events.api.deps import get_event_or_404
from app.modules.events.schemas.event_rsvp import RsvpResponse, RsvpSet
from app.modules.events.services.rsvp_service import remove_rsvp, set_rsvp

logger = structlog.get_logger()

router = APIRouter()


@router.put(
    "/{event_id}/rsvp",
    responses={404: {"description": "Event not found"}},
)
async def put_rsvp(
    event_id: UUID,
    body: RsvpSet,
    db: DBSession,
    user: CurrentUser,
) -> RsvpResponse:
    await get_event_or_404(db, event_id)
    rsvp = await set_rsvp(db, event_id, UUID(user.user_id), body.status)
    await db.commit()
    logger.info(
        "rsvp_set",
        event_id=str(event_id),
        user_id=user.user_id,
        status=body.status,
    )
    return RsvpResponse.model_validate(rsvp)


@router.delete(
    "/{event_id}/rsvp",
    status_code=204,
    responses={404: {"description": "Event not found"}},
)
async def delete_rsvp(
    event_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> None:
    await get_event_or_404(db, event_id)
    removed = await remove_rsvp(db, event_id, UUID(user.user_id))
    await db.commit()
    if removed:
        logger.info(
            "rsvp_removed",
            event_id=str(event_id),
            user_id=user.user_id,
        )
