"""Tests for events stats_service aggregation."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB
from app.modules.events.services.stats_service import get_stats


@pytest.mark.asyncio
async def test_total_cost_sums_other_costs_plus_attendee_costs(
    db_session: AsyncSession, debug_user: UserDB, test_user: UserDB
):
    event = EventDB(
        name="Stats Test",
        event_type="Conference",
        theme_primary="Climate",
        region_focus="Global",
        start_date=date(2026, 3, 10),
        other_costs=Decimal("500.00"),
    )
    db_session.add(event)
    await db_session.flush()
    db_session.add_all(
        [
            EventAttendeeDB(
                event_id=event.id,
                user_id=debug_user.id,
                role="Attendee",
                cost=Decimal("100.00"),
            ),
            EventAttendeeDB(
                event_id=event.id,
                user_id=test_user.id,
                role="Speaker",
                cost=Decimal("250.00"),
            ),
        ]
    )
    await db_session.commit()

    stats = await get_stats(db_session, year=2026)
    assert stats["total_cost"] == Decimal("850.00")


@pytest.mark.asyncio
async def test_total_cost_handles_null_attendee_costs(db_session: AsyncSession, debug_user: UserDB):
    event = EventDB(
        name="Null Costs",
        event_type="Conference",
        theme_primary="Climate",
        region_focus="Global",
        start_date=date(2026, 4, 1),
        other_costs=Decimal("300.00"),
    )
    db_session.add(event)
    await db_session.flush()
    db_session.add(
        EventAttendeeDB(
            event_id=event.id,
            user_id=debug_user.id,
            role="Attendee",
            cost=None,
        )
    )
    await db_session.commit()

    stats = await get_stats(db_session, year=2026)
    assert stats["total_cost"] == Decimal("300.00")


@pytest.mark.asyncio
async def test_total_cost_with_no_events(db_session: AsyncSession):
    stats = await get_stats(db_session, year=2026)
    assert stats["total_cost"] == 0
