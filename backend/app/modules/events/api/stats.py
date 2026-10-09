"""Event statistics endpoint."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.api.deps import DBSession
from app.modules.events.api.deps import EventsViewer
from app.modules.events.constants import ATTENDING_FILTER_PATTERN
from app.modules.events.services.stats_service import get_stats

router = APIRouter()


@router.get("/stats")
async def get_event_stats(
    db: DBSession,
    user: EventsViewer,
    year: int | None = None,
    attending: Annotated[str | None, Query(pattern=ATTENDING_FILTER_PATTERN)] = None,
) -> dict:
    return await get_stats(db, year=year, attending=attending)
