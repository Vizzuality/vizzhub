"""Event enum options endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.events.constants import AttendeeRole, EventType, RegionFocus, Theme

router = APIRouter()

EventsViewer = Annotated[TokenData, Depends(require_permission(Action.EVENTS_VIEW))]


@router.get("/options")
async def get_options(
    user: EventsViewer,
) -> dict:
    return {
        "event_types": [e.value for e in EventType],
        "themes": [e.value for e in Theme],
        "regions": [e.value for e in RegionFocus],
        "attendee_roles": [e.value for e in AttendeeRole],
    }
