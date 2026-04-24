"""Tests for rsvp_service."""

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.events.models.event import EventDB
from app.modules.events.services.rsvp_service import (
    get_rsvps_for_event,
    remove_rsvp,
    set_rsvp,
)


@pytest_asyncio.fixture
async def event(db_session: AsyncSession) -> EventDB:
    e = EventDB(
        name="RSVP Test", event_type="Conference", theme_primary="Climate",
        region_focus="Global", start_date=date(2026, 3, 1),
        other_costs=Decimal("0"),
    )
    db_session.add(e)
    await db_session.commit()
    await db_session.refresh(e)
    return e


@pytest.mark.asyncio
async def test_set_rsvp_inserts_when_new(
    db_session: AsyncSession, event: EventDB, debug_user: UserDB
):
    rsvp = await set_rsvp(db_session, event.id, debug_user.id, "going")
    await db_session.commit()
    assert rsvp.status == "going"


@pytest.mark.asyncio
async def test_set_rsvp_updates_when_exists(
    db_session: AsyncSession, event: EventDB, debug_user: UserDB
):
    await set_rsvp(db_session, event.id, debug_user.id, "going")
    await db_session.commit()
    updated = await set_rsvp(db_session, event.id, debug_user.id, "maybe")
    await db_session.commit()
    assert updated.status == "maybe"
    grouped = await get_rsvps_for_event(db_session, event.id)
    assert len(grouped["maybe"]) == 1
    assert grouped["going"] == []


@pytest.mark.asyncio
async def test_remove_rsvp_deletes(
    db_session: AsyncSession, event: EventDB, debug_user: UserDB
):
    await set_rsvp(db_session, event.id, debug_user.id, "going")
    await db_session.commit()
    await remove_rsvp(db_session, event.id, debug_user.id)
    await db_session.commit()
    grouped = await get_rsvps_for_event(db_session, event.id)
    assert grouped["going"] == []
