"""Event statistics aggregation service."""

from sqlalchemy import ColumnElement, and_, desc, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.user import UserDB
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB
from app.modules.events.services.event_service import attending_condition


def _event_filter(year: int | None, attending: str | None) -> ColumnElement:
    conditions = []
    if year is not None:
        conditions.append(func.extract("year", EventDB.start_date) == year)
    if attending:
        conditions.append(attending_condition(attending))
    return and_(true(), *conditions)


async def _group_count(
    db: AsyncSession,
    label_col: ColumnElement,
    event_filter: ColumnElement,
) -> list[dict]:
    stmt = (
        select(
            label_col.label("label"),
            func.count(EventDB.id).label("count"),
        )
        .where(event_filter)
        .group_by(label_col)
        .order_by(desc("count"))
    )
    result = await db.execute(stmt)
    return [{"label": row.label, "count": row.count} for row in result.all()]


async def _attendee_group_count(
    db: AsyncSession,
    label_col: ColumnElement,
    event_filter: ColumnElement,
) -> list[dict]:
    stmt = (
        select(
            label_col.label("label"),
            func.count(EventAttendeeDB.id).label("count"),
        )
        .select_from(EventAttendeeDB)
        .join(EventDB, EventDB.id == EventAttendeeDB.event_id)
        .where(event_filter)
        .group_by(label_col)
        .order_by(desc("count"))
    )
    result = await db.execute(stmt)
    return [{"label": row.label, "count": row.count} for row in result.all()]


async def _attendee_fa_count(
    db: AsyncSession,
    event_filter: ColumnElement,
) -> list[dict]:
    fa_alias = aliased(FunctionalAreaDB)
    user_alias = aliased(UserDB)
    stmt = (
        select(
            func.coalesce(fa_alias.name, "Unassigned").label("label"),
            func.count(EventAttendeeDB.id).label("count"),
        )
        .select_from(EventAttendeeDB)
        .join(EventDB, EventDB.id == EventAttendeeDB.event_id)
        .join(user_alias, user_alias.id == EventAttendeeDB.user_id)
        .outerjoin(fa_alias, fa_alias.id == user_alias.functional_area_id)
        .where(event_filter)
        .group_by(fa_alias.name)
        .order_by(desc("count"))
    )
    result = await db.execute(stmt)
    return [{"label": row.label, "count": row.count} for row in result.all()]


async def get_stats(
    db: AsyncSession,
    year: int | None = None,
    attending: str | None = None,
) -> dict:
    ef = _event_filter(year, attending)

    total_events_stmt = select(func.count(EventDB.id)).where(ef)
    total_events = (await db.execute(total_events_stmt)).scalar() or 0

    total_attendees_stmt = (
        select(func.count(func.distinct(EventAttendeeDB.user_id)))
        .select_from(EventAttendeeDB)
        .join(EventDB, EventDB.id == EventAttendeeDB.event_id)
        .where(ef)
    )
    total_attendees = (await db.execute(total_attendees_stmt)).scalar() or 0

    other_costs_sum = (
        await db.execute(select(func.coalesce(func.sum(EventDB.other_costs), 0)).where(ef))
    ).scalar() or 0
    attendees_cost_sum = (
        await db.execute(
            select(func.coalesce(func.sum(EventAttendeeDB.cost), 0))
            .select_from(EventAttendeeDB)
            .join(EventDB, EventDB.id == EventAttendeeDB.event_id)
            .where(ef)
        )
    ).scalar() or 0
    total_cost = other_costs_sum + attendees_cost_sum

    by_quarter = await _group_count(
        db,
        func.ceil(func.extract("month", EventDB.start_date) / 3),
        ef,
    )
    by_theme = await _group_count(db, EventDB.theme_primary, ef)
    by_type = await _group_count(db, EventDB.event_type, ef)
    by_region = await _group_count(db, EventDB.region_focus, ef)
    by_country = await _group_count(
        db,
        func.coalesce(EventDB.location_country, "Unknown"),
        ef,
    )
    by_role = await _attendee_group_count(db, EventAttendeeDB.role, ef)
    by_fa = await _attendee_fa_count(db, ef)

    return {
        "total_events": total_events,
        "total_attendees": total_attendees,
        "total_cost": total_cost,
        "by_quarter": by_quarter,
        "by_theme": by_theme,
        "by_type": by_type,
        "by_region": by_region,
        "by_country": by_country,
        "by_role": by_role,
        "by_fa": by_fa,
    }
