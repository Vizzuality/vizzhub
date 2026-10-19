"""Events data access — event list with attendees, and dashboard stats."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.public import get_stats as get_event_stats
from app.modules.events.public import list_events as list_event_rows
from app.modules.events.public import load_attendee_details

BASE_URL = "https://hub.vizzuality.com"
MAX_LIMIT = 200


def _money(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


async def list_events(
    session: AsyncSession,
    *,
    year: int | None = None,
    quarter: int | None = None,
    attending: str | None = None,
    theme: str | None = None,
    event_type: str | None = None,
    region: str | None = None,
    search: str | None = None,
    limit: int = 100,
) -> dict:
    """Events ordered by start date with attendees (role, FA, cost) and total cost."""
    limit = max(1, min(limit, MAX_LIMIT))
    items, total = await list_event_rows(
        session,
        search=search,
        year=year,
        quarter=quarter,
        event_type=event_type,
        theme_primary=theme,
        region_focus=region,
        attending=attending,
        sort_by="start_date",
        sort_dir="asc",
        limit=limit,
    )

    attendees = await load_attendee_details(session, [item["id"] for item in items])
    attendees_by_event: dict = {}
    for att in attendees:
        attendees_by_event.setdefault(att["event_id"], []).append({
            "user_id": str(att["user_id"]),
            "name": att["user_name"],
            "functional_area": att["functional_area"],
            "role": att["role"],
            "cost": _money(att["cost"]),
        })

    events = [
        {
            "event_id": str(item["id"]),
            "name": item["name"],
            "event_type": item["event_type"],
            "theme_primary": item["theme_primary"],
            "theme_secondary": item["theme_secondary"],
            "region_focus": item["region_focus"],
            "location_city": item["location_city"],
            "location_country": item["location_country"],
            "start_date": item["start_date"],
            "end_date": item["end_date"],
            "attending": item["attending"],
            "rating": item["rating"],
            "other_costs": _money(item["other_costs"]),
            "total_cost": _money(item["total_cost"]),
            "attendees": attendees_by_event.get(item["id"], []),
            "url": f"{BASE_URL}/events/{item['id']}",
        }
        for item in items
    ]
    return {"events": events, "total": total, "returned": len(events)}


async def get_stats(
    session: AsyncSession,
    *,
    year: int | None = None,
    attending: str | None = None,
) -> dict:
    """Dashboard aggregates: totals plus counts by quarter, theme, type, region, role, FA."""
    stats = await get_event_stats(session, year=year, attending=attending)
    stats["total_cost"] = _money(stats["total_cost"])
    return stats
