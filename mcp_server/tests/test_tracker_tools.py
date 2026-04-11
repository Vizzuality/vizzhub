"""Tests for MCP Tracker tools — tool response formatting via call_tool."""

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
    InvoiceDB,
    ProgressReportDB,
    ReportDB,
    ReportPartDB,
    ReportingPeriodDB,
)
from mcp_server.data.base import override_session
from mcp_server.server import create_mcp_server


def _parse_tool_result(result) -> dict | list:
    """Extract and parse JSON from MCP call_tool result."""
    content_blocks = result[0]
    return json.loads(content_blocks[0].text)


@pytest_asyncio.fixture
async def seed_tracker(db_session: AsyncSession) -> dict:
    """Seed a project with reports, invoices, and progress for tool tests."""
    fa = FunctionalAreaDB(name="Engineering")
    db_session.add(fa)
    await db_session.flush()

    user = UserDB(
        email="test@vizzuality.com",
        first_name="Test",
        last_name="User",
        functional_area_id=fa.id,
        active=True,
    )
    db_session.add(user)
    await db_session.flush()

    project = ProjectDB(
        name="Tool Test Project",
        code="TTP",
        status="live",
        is_billable=True,
        currency="euro",
        budget=Decimal("50000.00"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
        project_manager_id=user.id,
    )
    db_session.add(project)
    await db_session.flush()

    period = ReportingPeriodDB(
        date=date(2026, 1, 1),
        status="finished",
        base_rate=Decimal("175.00"),
    )
    db_session.add(period)
    await db_session.flush()

    report = ReportDB(
        user_id=user.id,
        reporting_period_id=period.id,
        estimated=False,
    )
    db_session.add(report)
    await db_session.flush()

    db_session.add(ReportPartDB(
        report_id=report.id,
        project_id=project.id,
        functional_area_id=fa.id,
        percentage=Decimal("0.5000"),
        days=Decimal("10.0000"),
        cost=Decimal("5000.00"),
    ))

    db_session.add(InvoiceDB(
        project_id=project.id,
        amount=Decimal("10000.00"),
        due_date=date(2026, 3, 1),
        milestone="M1",
        status="paid",
    ))

    db_session.add(ProgressReportDB(
        reporting_period_id=period.id,
        project_id=project.id,
        percentage=Decimal("0.2000"),
        delta=Decimal("0.2000"),
    ))

    await db_session.commit()
    return {"project_id": str(project.id), "period_id": str(period.id)}


@pytest.mark.asyncio
async def test_tracker_get_projects(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("tracker_get_projects", {})
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) >= 1
    project = data[0]
    assert project["name"] == "Tool Test Project"
    assert project["staff_cost"] == 5000.0
    assert project["income"] == 10000.0


@pytest.mark.asyncio
async def test_tracker_get_projects_with_filter(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("tracker_get_projects", {"status": "proposal"})
    data = _parse_tool_result(result)
    assert data == []


@pytest.mark.asyncio
async def test_tracker_get_project_detail(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "tracker_get_project_detail",
            {"project_id": seed_tracker["project_id"]},
        )
    data = _parse_tool_result(result)
    assert data["name"] == "Tool Test Project"
    assert data["cost_summary"]["staff_cost"] == 5000.0
    assert data["cost_summary"]["burn_percentage"] == 10.0


@pytest.mark.asyncio
async def test_tracker_get_project_detail_invalid_id(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "tracker_get_project_detail",
            {"project_id": "not-a-uuid"},
        )
    data = _parse_tool_result(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_tracker_get_project_time(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "tracker_get_project_time",
            {"project_id": seed_tracker["project_id"]},
        )
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["total_days"] == 10.0
    assert len(data[0]["periods"]) == 1


@pytest.mark.asyncio
async def test_tracker_get_project_time_by_fa(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "tracker_get_project_time",
            {"project_id": seed_tracker["project_id"], "group_by": "functional_area"},
        )
    data = _parse_tool_result(result)
    assert len(data) == 1
    assert data[0]["name"] == "Engineering"


@pytest.mark.asyncio
async def test_tracker_get_project_time_invalid_group(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "tracker_get_project_time",
            {"project_id": seed_tracker["project_id"], "group_by": "invalid"},
        )
    data = _parse_tool_result(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_tracker_get_project_invoices(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "tracker_get_project_invoices",
            {"project_id": seed_tracker["project_id"]},
        )
    data = _parse_tool_result(result)
    assert len(data) == 1
    assert data[0]["amount"] == 10000.0
    assert data[0]["status"] == "paid"


@pytest.mark.asyncio
async def test_tracker_get_project_progress(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "tracker_get_project_progress",
            {"project_id": seed_tracker["project_id"]},
        )
    data = _parse_tool_result(result)
    assert len(data) == 1
    assert data[0]["percentage"] == 0.2
    assert data[0]["delta"] == 0.2


@pytest.mark.asyncio
async def test_tracker_get_periods(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("tracker_get_periods", {})
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["status"] == "finished"
    assert data[0]["report_count"] == 1
    assert data[0]["confirmed_count"] == 1


@pytest.mark.asyncio
async def test_tracker_get_periods_with_filter(db_session, seed_tracker) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("tracker_get_periods", {"status": "active"})
    data = _parse_tool_result(result)
    assert data == []
