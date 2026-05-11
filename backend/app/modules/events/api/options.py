"""Event enum options endpoint."""

from fastapi import APIRouter
from sqlalchemy import desc, distinct, func, select

from app.core.api.deps import DBSession
from app.modules.events.api.deps import EventsViewer
from app.modules.events.constants import AttendeeRole, EventType, RegionFocus, Theme
from app.modules.events.models.event import EventDB

router = APIRouter()


@router.get("/options")
async def get_options(
    user: EventsViewer,
    db: DBSession,
) -> dict:
    year_col = func.extract("year", EventDB.start_date)
    years_stmt = (
        select(distinct(year_col))
        .order_by(desc(year_col))
    )
    years_rows = (await db.execute(years_stmt)).scalars().all()
    return {
        "event_types": [e.value for e in EventType],
        "themes": [e.value for e in Theme],
        "regions": [e.value for e in RegionFocus],
        "attendee_roles": [e.value for e in AttendeeRole],
        "years_with_data": [int(y) for y in years_rows if y is not None],
    }
