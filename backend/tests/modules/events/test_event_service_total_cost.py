"""Tests for event_service total_cost computation."""

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB
from app.modules.events.services.event_service import (
    get_event_with_attendees,
    list_events,
)


@pytest_asyncio.fixture
async def event_with_attendees(
    db_session: AsyncSession, debug_user: UserDB, test_user: UserDB
) -> EventDB:
    event = EventDB(
        name="Sum Test",
        event_type="Conference",
        theme_primary="Climate",
        region_focus="Global",
        start_date=date(2026, 1, 15),
        other_costs=Decimal("500.00"),
    )
    db_session.add(event)
    await db_session.flush()
    db_session.add_all([
        EventAttendeeDB(
            event_id=event.id, user_id=debug_user.id,
            role="Attendee", cost=Decimal("100.00"),
        ),
        EventAttendeeDB(
            event_id=event.id, user_id=test_user.id,
            role="Speaker", cost=None,
        ),
    ])
    await db_session.commit()
    return event


@pytest.mark.asyncio
async def test_get_event_total_cost_sums_attendees_and_other(
    db_session: AsyncSession, event_with_attendees: EventDB
):
    data = await get_event_with_attendees(event_with_attendees.id, db_session)
    assert data is not None
    assert data["total_cost"] == Decimal("600.00")
    assert data["other_costs"] == Decimal("500.00")


@pytest.mark.asyncio
async def test_list_events_includes_total_cost(
    db_session: AsyncSession, event_with_attendees: EventDB
):
    items, _ = await list_events(db_session)
    assert len(items) == 1
    assert items[0]["total_cost"] == Decimal("600.00")


@pytest.mark.asyncio
async def test_list_events_sort_by_total_cost_desc(
    db_session: AsyncSession, debug_user: UserDB
):
    cheap = EventDB(
        name="Cheap", event_type="Conference", theme_primary="Climate",
        region_focus="Global", start_date=date(2026, 2, 1),
        other_costs=Decimal("10.00"),
    )
    pricey = EventDB(
        name="Pricey", event_type="Conference", theme_primary="Climate",
        region_focus="Global", start_date=date(2026, 2, 2),
        other_costs=Decimal("1000.00"),
    )
    db_session.add_all([cheap, pricey])
    await db_session.commit()

    items, _ = await list_events(
        db_session, sort_by="total_cost", sort_dir="desc",
    )
    assert [i["name"] for i in items] == ["Pricey", "Cheap"]
