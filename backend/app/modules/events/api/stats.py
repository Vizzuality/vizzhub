"""Event statistics endpoint."""

from fastapi import APIRouter

from app.core.api.deps import DBSession
from app.modules.events.api.deps import EventsViewer
from app.modules.events.services.stats_service import get_stats

router = APIRouter()


@router.get("/stats")
async def get_event_stats(
    db: DBSession,
    user: EventsViewer,
    year: int | None = None,
) -> dict:
    return await get_stats(db, year=year)
