"""Tests for MCP Events tools — list with attendees and dashboard stats."""

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.user import UserDB
from app.modules.events.models.event import EventDB
from app.modules.events.models.event_attendee import EventAttendeeDB
from mcp_server.data.base import override_mcp_user, override_session
from mcp_server.server import create_mcp_server


def _parse_tool_result(result) -> dict | list:
    return json.loads(result[0][0].text)


@pytest_asyncio.fixture
async def seed_events(db_session: AsyncSession) -> dict:
    fa = FunctionalAreaDB(name="Project Manager")
    db_session.add(fa)
    await db_session.flush()
    speaker = UserDB(
        email="speaker@example.com", first_name="Ana", last_name="Speaker",
        functional_area_id=fa.id, active=True,
    )
    attendee = UserDB(email="attendee@example.com", first_name="Bo", last_name="Attendee", active=True)
    db_session.add_all([speaker, attendee])
    await db_session.flush()

    past = EventDB(
        name="Climate Summit", event_type="Summit", theme_primary="Climate",
        region_focus="Europe", location_country="Spain",
        start_date=date.today() - timedelta(days=30), other_costs=Decimal("500.00"),
        attending="yes",
    )
    future = EventDB(
        name="Ocean Forum", event_type="Forum", theme_primary="Oceans & Water",
        region_focus="Global", start_date=date.today() + timedelta(days=30),
        other_costs=Decimal("0"), attending="yes",
    )
    skipped = EventDB(
        name="Skipped Expo", event_type="Exhibition / Expo", theme_primary="Climate",
        region_focus="Europe", start_date=date.today() - timedelta(days=10),
        other_costs=Decimal("0"), attending="no",
    )
    db_session.add_all([past, future, skipped])
    await db_session.flush()
    db_session.add_all([
        EventAttendeeDB(event_id=past.id, user_id=speaker.id, role="Speaker", cost=Decimal("1200.00")),
        EventAttendeeDB(event_id=past.id, user_id=attendee.id, role="Attendee", cost=None),
        EventAttendeeDB(event_id=future.id, user_id=attendee.id, role="Attendee", cost=Decimal("300")),
    ])
    await db_session.commit()
    return {"past_id": str(past.id)}


@pytest.mark.asyncio
async def test_events_list_returns_attendees_with_role_fa_and_cost(db_session, seed_events) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("events_list", {"attending": "attended"})
    data = _parse_tool_result(result)
    assert data["total"] == 1
    event = data["events"][0]
    assert event["event_id"] == seed_events["past_id"]
    assert event["total_cost"] == 1700.0
    assert event["url"].endswith(f"/events/{seed_events['past_id']}")
    by_name = {a["name"]: a for a in event["attendees"]}
    speaker = by_name["Ana Speaker"]
    assert speaker["role"] == "Speaker"
    assert speaker["functional_area"] == "Project Manager"
    assert speaker["cost"] == 1200.0
    assert by_name["Bo Attendee"]["functional_area"] is None
    assert by_name["Bo Attendee"]["cost"] is None


@pytest.mark.asyncio
async def test_events_list_filters_by_theme(db_session, seed_events) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("events_list", {"theme": "Climate"})
    names = [e["name"] for e in _parse_tool_result(result)["events"]]
    assert sorted(names) == ["Climate Summit", "Skipped Expo"]


@pytest.mark.asyncio
async def test_events_list_rejects_unknown_attending(db_session, seed_events) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        with pytest.raises(ToolError):
            await server.call_tool("events_list", {"attending": "perhaps"})


@pytest.mark.asyncio
async def test_events_get_stats(db_session, seed_events) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("events_get_stats", {"attending": "yes"})
    data = _parse_tool_result(result)
    assert data["total_events"] == 2
    assert data["total_attendees"] == 2
    assert data["total_cost"] == 2000.0
    assert {r["label"]: r["count"] for r in data["by_role"]} == {"Attendee": 2, "Speaker": 1}


@pytest.mark.asyncio
async def test_events_tools_require_events_view(db_session, seed_events, restricted_user) -> None:
    server = create_mcp_server()
    async with override_session(db_session), override_mcp_user(restricted_user):
        for tool in ("events_list", "events_get_stats"):
            with pytest.raises(ToolError, match="Permission denied"):
                await server.call_tool(tool, {})
