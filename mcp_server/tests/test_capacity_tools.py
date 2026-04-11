"""Tests for MCP Capacity tools — tool response formatting via call_tool."""

import json
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models import (
    ReportDB,
    ReportPartDB,
    ReportingPeriodDB,
)
from mcp_server.data.base import override_session
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


@pytest.mark.asyncio
async def test_capacity_get_insights(db_session, seed_capacity) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "capacity_get_insights",
            {"start_month": "2026-01", "end_month": "2026-01"},
        )
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) >= 1
    period = data[0]
    assert period["period"] == "2026-01"
    fa_shorts = [fa["short"] for fa in period["functional_areas"]]
    assert "FE" in fa_shorts or "BE" in fa_shorts


@pytest.mark.asyncio
async def test_capacity_get_fa_detail(db_session, seed_capacity) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "capacity_get_fa_detail",
            {"fa": "FE", "start_month": "2026-01", "end_month": "2026-01"},
        )
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    if data:
        assert "users" in data[0]


@pytest.mark.asyncio
async def test_capacity_get_fa_detail_invalid_fa(db_session, seed_capacity) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "capacity_get_fa_detail",
            {"fa": "INVALID"},
        )
    data = _parse_tool_result(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_capacity_get_user_detail(db_session, seed_capacity) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "capacity_get_user_detail",
            {
                "user_id": seed_capacity["user_fe_id"],
                "start_month": "2026-01",
                "end_month": "2026-01",
            },
        )
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    if data:
        assert "projects" in data[0]


@pytest.mark.asyncio
async def test_capacity_get_allocation(db_session, seed_capacity) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("capacity_get_allocation", {})
    data = _parse_tool_result(result)
    assert "periods_used" in data
    assert "users" in data


@pytest.mark.asyncio
async def test_capacity_get_allocation_projects(db_session, seed_capacity) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "capacity_get_allocation", {"view": "projects"},
        )
    data = _parse_tool_result(result)
    assert "periods_used" in data
    assert "projects" in data


@pytest.mark.asyncio
async def test_capacity_get_allocation_invalid_view(db_session, seed_capacity) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "capacity_get_allocation", {"view": "bad"},
        )
    data = _parse_tool_result(result)
    assert "error" in data
