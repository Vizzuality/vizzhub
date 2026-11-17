"""Tests for MCP Capacity tools — tool response formatting via call_tool."""

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.capacity.public import CapacityPlanDB
from app.modules.tracker.models import (
    ReportDB,
    ReportPartDB,
    ReportingPeriodDB,
)
from mcp_server.data.base import override_session
from mcp_server.data.capacity import current_monday
from mcp_server.server import create_mcp_server


def _parse_tool_result(result) -> dict | list:
    content_blocks = result[0]
    return json.loads(content_blocks[0].text)


@pytest_asyncio.fixture
async def seed_capacity(db_session: AsyncSession) -> dict:
    """Seed users, projects, and reports for capacity tests."""
    fa_fe = FunctionalAreaDB(name="Frontend Developer")
    fa_be = FunctionalAreaDB(name="Backend Developer")
    db_session.add_all([fa_fe, fa_be])
    await db_session.flush()

    user_fe = UserDB(
        email="fe@vizzuality.com",
        first_name="Alice",
        last_name="Dev",
        functional_area_id=fa_fe.id,
        active=True,
        requires_project_reporting=True,
    )
    user_be = UserDB(
        email="be@vizzuality.com",
        first_name="Bob",
        last_name="End",
        functional_area_id=fa_be.id,
        active=True,
        requires_project_reporting=True,
    )
    db_session.add_all([user_fe, user_be])
    await db_session.flush()

    proj_billable = ProjectDB(
        name="Billable Project",
        code="BP1",
        status="live",
        is_billable=True,
    )
    proj_absence = ProjectDB(
        name="Holidays",
        code="HOL",
        status="live",
        is_billable=False,
        is_absence=True,
    )
    db_session.add_all([proj_billable, proj_absence])
    await db_session.flush()

    period = ReportingPeriodDB(
        date=date(2026, 1, 1),
        status="finished",
        base_rate=Decimal("175.00"),
    )
    db_session.add(period)
    await db_session.flush()

    # FE user: 60% billable, 10% absence
    report_fe = ReportDB(
        user_id=user_fe.id,
        reporting_period_id=period.id,
        estimated=False,
    )
    db_session.add(report_fe)
    await db_session.flush()

    db_session.add(ReportPartDB(
        report_id=report_fe.id,
        project_id=proj_billable.id,
        functional_area_id=fa_fe.id,
        percentage=Decimal("0.6000"),
        days=Decimal("12.0"),
        cost=Decimal("6000.00"),
    ))
    db_session.add(ReportPartDB(
        report_id=report_fe.id,
        project_id=proj_absence.id,
        functional_area_id=fa_fe.id,
        percentage=Decimal("0.1000"),
        days=Decimal("2.0"),
        cost=Decimal("0.00"),
    ))

    # BE user: 80% billable
    report_be = ReportDB(
        user_id=user_be.id,
        reporting_period_id=period.id,
        estimated=False,
    )
    db_session.add(report_be)
    await db_session.flush()

    db_session.add(ReportPartDB(
        report_id=report_be.id,
        project_id=proj_billable.id,
        functional_area_id=fa_be.id,
        percentage=Decimal("0.8000"),
        days=Decimal("16.0"),
        cost=Decimal("8000.00"),
    ))

    await db_session.commit()
    return {
        "user_fe_id": str(user_fe.id),
        "user_be_id": str(user_be.id),
        "project_id": str(proj_billable.id),
    }


async def _call(db_session, name: str, args: dict) -> dict:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(name, args)
    return _parse_tool_result(result)


# ---------------------------------------------------------------------------
# PAST — confirmed reports
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reported_overview(db_session, seed_capacity) -> None:
    data = await _call(
        db_session,
        "capacity_get_reported_overview",
        {"start_month": "2026-01", "end_month": "2026-01"},
    )
    assert data["last_closed_month"] == "2026-01"
    assert "confirmed" in data["data_source"].lower()
    period = data["periods"][0]
    assert period["period"] == "2026-01"
    fa_shorts = [fa["short"] for fa in period["functional_areas"]]
    assert "FE" in fa_shorts or "BE" in fa_shorts


@pytest.mark.asyncio
async def test_reported_overview_truncates_at_last_closed_month(db_session, seed_capacity) -> None:
    data = await _call(
        db_session,
        "capacity_get_reported_overview",
        {"start_month": "2026-01", "end_month": "2026-06"},
    )
    assert [p["period"] for p in data["periods"]] == ["2026-01"]
    assert "capacity_get_planned" in data["note"]


@pytest.mark.asyncio
async def test_reported_excludes_open_periods(db_session, seed_capacity) -> None:
    """An active (not closed) period has no confirmed data yet, even with reports."""
    db_session.add(
        ReportingPeriodDB(date=date(2026, 2, 1), status="active", base_rate=Decimal("175.00"))
    )
    await db_session.commit()
    data = await _call(
        db_session,
        "capacity_get_reported_overview",
        {"start_month": "2026-01", "end_month": "2026-02"},
    )
    assert [p["period"] for p in data["periods"]] == ["2026-01"]


@pytest.mark.asyncio
async def test_reported_future_range_redirects_to_planner(db_session, seed_capacity) -> None:
    data = await _call(
        db_session,
        "capacity_get_reported_by_fa",
        {"fa": "FE", "start_month": "2026-03", "end_month": "2026-05"},
    )
    assert data["periods"] == []
    assert "capacity_get_planned" in data["note"]


@pytest.mark.asyncio
async def test_reported_by_fa(db_session, seed_capacity) -> None:
    data = await _call(
        db_session,
        "capacity_get_reported_by_fa",
        {"fa": "FE", "start_month": "2026-01", "end_month": "2026-01"},
    )
    assert data["periods"]
    assert "users" in data["periods"][0]


@pytest.mark.asyncio
async def test_reported_by_fa_invalid_fa(db_session, seed_capacity) -> None:
    with pytest.raises(ToolError, match="Invalid fa"):
        await _call(db_session, "capacity_get_reported_by_fa", {"fa": "INVALID"})


@pytest.mark.asyncio
async def test_reported_by_user(db_session, seed_capacity) -> None:
    data = await _call(
        db_session,
        "capacity_get_reported_by_user",
        {
            "user_id": seed_capacity["user_fe_id"],
            "start_month": "2026-01",
            "end_month": "2026-01",
        },
    )
    assert data["periods"]
    assert "projects" in data["periods"][0]


@pytest.mark.asyncio
async def test_reported_average(db_session, seed_capacity) -> None:
    data = await _call(db_session, "capacity_get_reported_average", {})
    assert "periods_used" in data
    assert "users" in data
    assert data["last_closed_month"] == "2026-01"


@pytest.mark.asyncio
async def test_reported_average_projects(db_session, seed_capacity) -> None:
    data = await _call(db_session, "capacity_get_reported_average", {"view": "projects"})
    assert "periods_used" in data
    assert "projects" in data


@pytest.mark.asyncio
async def test_reported_average_invalid_view(db_session, seed_capacity) -> None:
    with pytest.raises(ToolError, match="Invalid view"):
        await _call(db_session, "capacity_get_reported_average", {"view": "bad"})


# ---------------------------------------------------------------------------
# FUTURE — planner
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seed_plan(db_session: AsyncSession, seed_capacity: dict) -> dict:
    """Plan rows for last week (must never be returned), this week and next week."""
    monday = current_monday()
    user_id = seed_capacity["user_fe_id"]
    project_id = seed_capacity["project_id"]
    rows = [
        (monday - timedelta(weeks=1), 40),
        (monday, 60),
        (monday + timedelta(weeks=1), 120),
    ]
    for week, pct in rows:
        db_session.add(
            CapacityPlanDB(
                project_id=project_id,
                user_id=user_id,
                week_start=week,
                percentage=pct,
                created_by=user_id,
                updated_by=user_id,
            )
        )
    await db_session.commit()
    return {"monday": monday, "user_id": user_id, "project_id": project_id}


@pytest.mark.asyncio
async def test_planned_starts_at_current_week(db_session, seed_plan) -> None:
    monday = seed_plan["monday"]
    data = await _call(db_session, "capacity_get_planned", {})
    assert data["range"]["first_week"] == monday.isoformat()
    (assignment,) = data["assignments"]
    assert assignment["kind"] == "billable"
    assert assignment["weeks"] == {
        monday.isoformat(): 60,
        (monday + timedelta(weeks=1)).isoformat(): 120,
    }
    assert data["overallocated_weeks"] == [
        {
            "user_id": seed_plan["user_id"],
            "user_name": assignment["user_name"],
            "week": (monday + timedelta(weeks=1)).isoformat(),
            "total_percentage": 120,
        }
    ]


@pytest.mark.asyncio
async def test_planned_clamps_past_start(db_session, seed_plan) -> None:
    past = (seed_plan["monday"] - timedelta(weeks=4)).isoformat()
    data = await _call(db_session, "capacity_get_planned", {"start": past})
    assert data["range"]["first_week"] == seed_plan["monday"].isoformat()
    assert "capacity_get_reported" in data["note"]


@pytest.mark.asyncio
async def test_planned_past_range_redirects_to_reports(db_session, seed_plan) -> None:
    end = (seed_plan["monday"] - timedelta(days=1)).isoformat()
    data = await _call(db_session, "capacity_get_planned", {"start": "2026-01", "end": end})
    assert data["assignments"] == []
    assert "capacity_get_reported" in data["note"]


@pytest.mark.asyncio
async def test_planned_filters(db_session, seed_plan, seed_capacity) -> None:
    by_user = await _call(
        db_session, "capacity_get_planned", {"user_id": seed_capacity["user_be_id"]}
    )
    assert by_user["assignments"] == []
    by_fa = await _call(db_session, "capacity_get_planned", {"fa": "FE"})
    assert len(by_fa["assignments"]) == 1
    by_other_fa = await _call(db_session, "capacity_get_planned", {"fa": "BE"})
    assert by_other_fa["assignments"] == []
