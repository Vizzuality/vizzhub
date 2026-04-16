"""Event enum options endpoint."""

from fastapi import APIRouter

from app.modules.events.api.deps import EventsViewer
from app.modules.events.constants import AttendeeRole, EventType, RegionFocus, Theme

router = APIRouter()


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
