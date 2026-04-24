"""Tests for RSVP endpoints."""

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.models.event import EventDB


@pytest_asyncio.fixture
async def event(db_session: AsyncSession) -> EventDB:
    e = EventDB(
        name="RSVP Evt", event_type="Conference", theme_primary="Climate",
        region_focus="Global", start_date=date(2026, 8, 1),
        other_costs=Decimal("0"),
    )
    db_session.add(e)
    await db_session.commit()
    await db_session.refresh(e)
    return e


@pytest.mark.asyncio
async def test_put_rsvp_creates(client: AsyncClient, event: EventDB):
    r = await client.put(
        f"/api/events/{event.id}/rsvp",
        json={"status": "going"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "going"


@pytest.mark.asyncio
async def test_put_rsvp_updates_existing(client: AsyncClient, event: EventDB):
    await client.put(f"/api/events/{event.id}/rsvp", json={"status": "going"})
    r = await client.put(f"/api/events/{event.id}/rsvp", json={"status": "maybe"})
    assert r.status_code == 200
    assert r.json()["status"] == "maybe"


@pytest.mark.asyncio
async def test_delete_rsvp_removes(client: AsyncClient, event: EventDB):
    await client.put(f"/api/events/{event.id}/rsvp", json={"status": "going"})
    r = await client.delete(f"/api/events/{event.id}/rsvp")
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_put_rsvp_invalid_status(client: AsyncClient, event: EventDB):
    r = await client.put(
        f"/api/events/{event.id}/rsvp",
        json={"status": "attending"},
    )
    # The repo's global validation handler returns 400, not 422.
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_rsvp_counts_reflected_in_detail(
    client: AsyncClient, event: EventDB
):
    await client.put(f"/api/events/{event.id}/rsvp", json={"status": "going"})
    r = await client.get(f"/api/events/{event.id}")
    body = r.json()
    assert body["rsvp_counts"]["going"] == 1
    assert body["my_rsvp_status"] == "going"
    assert len(body["rsvps"]["going"]) == 1
