"""Tests for MCP Scorecard tools — tool response formatting via call_tool."""

import json
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.scorecard.models.global_metrics import GlobalMetricsDB
from app.modules.scorecard.models.metrics.db import MetricsDB
from mcp_server.data.base import override_session
from mcp_server.server import create_mcp_server


def _parse_tool_result(result) -> dict | list:
    """Extract and parse JSON from MCP call_tool result."""
    content_blocks = result[0]
    return json.loads(content_blocks[0].text)


@pytest_asyncio.fixture
async def seed_scorecard(db_session: AsyncSession) -> dict:
    """Seed a scored project with metrics and global metrics."""
    project = ProjectDB(
        name="Scorecard Test",
        code="SCT",
        status="live",
        is_billable=True,
        has_scorecard=True,
        budget=Decimal("50000.00"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 30),
    )
    db_session.add(project)
    await db_session.flush()

    metrics = MetricsDB(
        project_id=project.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        period_year=2026,
        period_month=1,
        snapshot_type="cumulative",
        budget_total=50000.0,
        cost_to_date=15000.0,
        percent_completed=0.30,
        percent_planned=0.17,
        bugs_total=3,
        tasks_completed=40,
        lead_time_days=2.0,
    )
    db_session.add(metrics)

    global_m = GlobalMetricsDB(
        period_year=2026,
        period_month=1,
        project_count=5,
        score=70.0,
        score_count=5,
        p_quality=75.0,
        p_quality_count=5,
        spi=0.82,
        spi_count=4,
    )
    db_session.add(global_m)
    await db_session.commit()

    return {"project_id": str(project.id)}


@pytest.mark.asyncio
async def test_scorecard_get_project_scores(db_session, seed_scorecard) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("scorecard_get_project_scores", {})
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) >= 1
    project = data[0]
    assert project["name"] == "Scorecard Test"
    assert project["score"] is not None


@pytest.mark.asyncio
async def test_scorecard_get_project_scores_filter(db_session, seed_scorecard) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "scorecard_get_project_scores", {"status": "finished"},
        )
    data = _parse_tool_result(result)
    assert data == []


@pytest.mark.asyncio
async def test_scorecard_get_project_scorecard(db_session, seed_scorecard) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "scorecard_get_project_scorecard",
            {"project_id": seed_scorecard["project_id"]},
        )
    data = _parse_tool_result(result)
    assert data["period"] == "2026-01"
    assert data["score"] is not None
    assert "dimensions" in data
    assert "indicators" in data
    assert "evm" in data


@pytest.mark.asyncio
async def test_scorecard_get_project_scorecard_invalid_id(db_session, seed_scorecard) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "scorecard_get_project_scorecard",
            {"project_id": "bad-uuid"},
        )
    data = _parse_tool_result(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_scorecard_get_project_history(db_session, seed_scorecard) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "scorecard_get_project_history",
            {"project_id": seed_scorecard["project_id"]},
        )
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["period"] == "2026-01"
    assert data[0]["score"] is not None


@pytest.mark.asyncio
async def test_scorecard_get_global_metrics(db_session, seed_scorecard) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("scorecard_get_global_metrics", {})
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["period"] == "2026-01"
    assert data[0]["project_count"] == 5


@pytest.mark.asyncio
async def test_scorecard_get_global_metrics_with_limit(db_session, seed_scorecard) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "scorecard_get_global_metrics", {"limit": 1},
        )
    data = _parse_tool_result(result)
    assert len(data) == 1
