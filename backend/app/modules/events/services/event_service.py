"""Event query and management service."""

from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import Label

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.user import UserDB
from app.core.sql_helpers import user_display_name_expr
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB


EVENT_FIELDS = [
    "id", "name", "event_type", "theme_primary", "theme_secondary",
    "region_focus", "location_city", "location_country", "start_date",
    "end_date", "other_costs", "rating", "url", "observations", "attending",
    "created_by", "created_at", "updated_at",
]


def event_to_dict(event: EventDB) -> dict:
    return {field: getattr(event, field) for field in EVENT_FIELDS}


def _attendee_count_subquery() -> Select:
    return (
        select(func.count(EventAttendeeDB.id))
        .where(EventAttendeeDB.event_id == EventDB.id)
        .correlate(EventDB)
        .scalar_subquery()
        .label("attendee_count")
    )


def _attendees_cost_subquery() -> Select:
    return (
        select(func.coalesce(func.sum(EventAttendeeDB.cost), 0))
        .where(EventAttendeeDB.event_id == EventDB.id)
        .correlate(EventDB)
        .scalar_subquery()
        .label("attendees_cost")
    )


def _total_cost_expr() -> Label:
    return (EventDB.other_costs + _attendees_cost_subquery()).label("total_cost")


SORT_COLUMNS = {
    "start_date": EventDB.start_date,
    "name": EventDB.name,
    "total_cost": _total_cost_expr(),
    "rating": EventDB.rating,
}


def _base_list_query() -> Select:
    return select(
        EventDB,
        _attendee_count_subquery(),
        _attendees_cost_subquery(),
    )


def apply_filters(
    stmt: Select,
    *,
    search: str | None = None,
    year: int | None = None,
    quarter: int | None = None,
    event_type: str | None = None,
    theme_primary: str | None = None,
    region_focus: str | None = None,
    location_country: str | None = None,
    attending: str | None = None,
) -> Select:
    if search:
        stmt = stmt.where(EventDB.name.ilike(f"%{search}%"))
    if year:
        stmt = stmt.where(
            func.extract("year", EventDB.start_date) == year
        )
    if quarter:
        stmt = stmt.where(
            func.ceil(func.extract("month", EventDB.start_date) / 3) == quarter
        )
    if event_type:
        stmt = stmt.where(EventDB.event_type == event_type)
    if theme_primary:
        stmt = stmt.where(EventDB.theme_primary == theme_primary)
    if region_focus:
        stmt = stmt.where(EventDB.region_focus == region_focus)
    if location_country:
        stmt = stmt.where(EventDB.location_country == location_country)
    if attending == "maybe":
        stmt = stmt.where(
            or_(EventDB.attending == "maybe", EventDB.attending.is_(None))
        )
    elif attending in ("yes", "no"):
        stmt = stmt.where(EventDB.attending == attending)
    return stmt


def apply_sort(stmt: Select, sort_by: str | None, sort_dir: str | None) -> Select:
    col = SORT_COLUMNS.get(sort_by or "start_date", EventDB.start_date)
    if sort_dir == "asc":
        return stmt.order_by(col.asc().nulls_last())
    return stmt.order_by(col.desc().nulls_last())


def _attendee_detail_query(
    event_ids: list[UUID],
    attendee_ids: list[UUID] | None = None,
) -> Select:
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
        .where(EventAttendeeDB.event_id.in_(event_ids))
        .order_by(EventAttendeeDB.role, user_display_name_expr(user_alias))
    )
    if attendee_ids is not None:
        stmt = stmt.where(EventAttendeeDB.id.in_(attendee_ids))
    return stmt


def _attendee_row_to_dict(att, user_name, user_email, functional_area) -> dict:
    return {
        "id": att.id,
        "event_id": att.event_id,
        "user_id": att.user_id,
        "role": att.role,
        "cost": att.cost,
        "user_name": user_name,
        "user_email": user_email,
        "functional_area": functional_area,
        "created_at": att.created_at,
    }


async def load_attendee_details(
    db: AsyncSession,
    event_ids: list[UUID],
    attendee_ids: list[UUID] | None = None,
) -> list[dict]:
    if not event_ids:
        return []
    result = await db.execute(_attendee_detail_query(event_ids, attendee_ids))
    return [_attendee_row_to_dict(*row) for row in result.all()]


async def _load_attendee_names_map(
    db: AsyncSession, event_ids: list[UUID]
) -> dict[UUID, list[str]]:
    if not event_ids:
        return {}
    user_alias = aliased(UserDB)
    stmt = (
        select(
            EventAttendeeDB.event_id,
            user_display_name_expr(user_alias).label("name"),
        )
        .join(user_alias, user_alias.id == EventAttendeeDB.user_id)
        .where(EventAttendeeDB.event_id.in_(event_ids))
        .order_by(user_display_name_expr(user_alias))
    )
    result = (await db.execute(stmt)).all()
    out: dict[UUID, list[str]] = {eid: [] for eid in event_ids}
    for event_id, name in result:
        out[event_id].append(name)
    return out


async def list_events(
    db: AsyncSession,
    *,
    viewer_id: UUID | None,
    search: str | None = None,
    year: int | None = None,
    quarter: int | None = None,
    event_type: str | None = None,
    theme_primary: str | None = None,
    region_focus: str | None = None,
    location_country: str | None = None,
    attending: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[dict], int]:
    filter_kwargs = dict(
        search=search, year=year, quarter=quarter, event_type=event_type,
        theme_primary=theme_primary, region_focus=region_focus,
        location_country=location_country, attending=attending,
    )

    base = _base_list_query()
    filtered = apply_filters(base, **filter_kwargs)
    sorted_stmt = apply_sort(filtered, sort_by, sort_dir)
    paginated = sorted_stmt.offset(offset).limit(limit)

    rows = (await db.execute(paginated)).all()

    count_stmt = select(func.count()).select_from(EventDB)
    count_stmt = apply_filters(count_stmt, **filter_kwargs)
    total = (await db.execute(count_stmt)).scalar() or 0

    event_ids = [row[0].id for row in rows]
    attendee_names_map = await _load_attendee_names_map(db, event_ids)

    items = []
    for event, attendee_count, attendees_cost in rows:
        data = event_to_dict(event)
        data["attendee_count"] = attendee_count or 0
        data["attendee_names"] = attendee_names_map.get(event.id, [])
        data["total_cost"] = event.other_costs + (attendees_cost or 0)
        items.append(data)

    return items, total


async def get_event_with_attendees(
    event_id: UUID,
    db: AsyncSession,
    viewer_id: UUID | None = None,
) -> dict | None:
    row = (
        await db.execute(_base_list_query().where(EventDB.id == event_id))
    ).one_or_none()
    if not row:
        return None

    event, attendee_count, attendees_cost = row
    attendees = await load_attendee_details(db, [event_id])

    data = event_to_dict(event)
    data["attendee_count"] = attendee_count or 0
    data["attendees"] = attendees
    data["total_cost"] = event.other_costs + (attendees_cost or 0)
    return data
