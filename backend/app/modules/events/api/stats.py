"""Event statistics endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.events.services.stats_service import get_stats

router = APIRouter()

EventsViewer = Annotated[TokenData, Depends(require_permission(Action.EVENTS_VIEW))]


@router.get("/stats")
async def get_event_stats(
    db: DBSession,
    user: EventsViewer,
    year: int | None = None,
) -> dict:
    return await get_stats(db, year=year)
