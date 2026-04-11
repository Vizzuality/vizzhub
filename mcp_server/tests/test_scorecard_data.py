"""Tests for mcp_server.data.scorecard — project scores and global metrics."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.scorecard.models.global_metrics import GlobalMetricsDB
from app.modules.scorecard.models.metrics.db import MetricsDB


@pytest_asyncio.fixture
async def project_scored(db_session: AsyncSession) -> ProjectDB:
    project = ProjectDB(
        name="Scored Project",
        code="SP1",
        status="live",
        is_billable=True,
        has_scorecard=True,
        budget=Decimal("100000.00"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def project_no_scorecard(db_session: AsyncSession) -> ProjectDB:
    project = ProjectDB(
        name="No Scorecard Project",
        code="NS1",
        status="live",
        is_billable=True,
        has_scorecard=False,
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def seed_metrics(
    db_session: AsyncSession,
    project_scored: ProjectDB,
) -> list[MetricsDB]:
    """Seed metrics for Jan and Feb 2026."""
    jan = MetricsDB(
        project_id=project_scored.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        period_year=2026,
        period_month=1,
        snapshot_type="cumulative",
        budget_total=100000.0,
        cost_to_date=25000.0,
        percent_completed=0.25,
        percent_planned=0.08,
        bugs_total=5,
        tasks_completed=50,
        lead_time_days=3.0,
        commitment_reliability=0.85,
    )
    feb = MetricsDB(
        project_id=project_scored.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 2, 28),
        period_year=2026,
        period_month=2,
        snapshot_type="cumulative",
        budget_total=100000.0,
        cost_to_date=50000.0,
        percent_completed=0.50,
        percent_planned=0.17,
        bugs_total=8,
        tasks_completed=100,
        lead_time_days=2.5,
        commitment_reliability=0.90,
    )
    db_session.add_all([jan, feb])
    await db_session.commit()
    return [jan, feb]


# ---- get_project_scores ----

@pytest.mark.asyncio
async def test_get_project_scores_excludes_no_scorecard(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    project_no_scorecard: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_scores

    result = await get_project_scores(db_session)
    names = [p["name"] for p in result]
    assert "Scored Project" in names
    assert "No Scorecard Project" not in names


@pytest.mark.asyncio
async def test_get_project_scores_returns_score(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_scores

    result = await get_project_scores(db_session)
    scored = next(p for p in result if p["name"] == "Scored Project")
    assert scored["score"] is not None
    assert 0 <= scored["score"] <= 100
    assert scored["dimensions"] is not None
    assert scored["period"] == "2026-02"


@pytest.mark.asyncio
async def test_get_project_scores_filter_by_status(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_scores

    result = await get_project_scores(db_session, status="proposal")
    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_project_scores_no_metrics(
    db_session: AsyncSession,
    project_scored: ProjectDB,
) -> None:
    await db_session.commit()
    from mcp_server.data.scorecard import get_project_scores

    result = await get_project_scores(db_session)
    scored = next(p for p in result if p["name"] == "Scored Project")
    assert scored["score"] is None
    assert scored["dimensions"] is None


# ---- get_project_scorecard ----

@pytest.mark.asyncio
async def test_get_project_scorecard_latest(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_scorecard

    result = await get_project_scorecard(db_session, project_scored.id)
    assert result is not None
    assert "error" not in result
    assert result["period"] == "2026-02"
    assert result["score"] is not None
    assert "dimensions" in result
    assert "indicators" in result
    assert result["project"]["name"] == "Scored Project"


@pytest.mark.asyncio
async def test_get_project_scorecard_specific_period(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_scorecard

    result = await get_project_scorecard(db_session, project_scored.id, year=2026, month=1)
    assert result is not None
    assert result["period"] == "2026-01"


@pytest.mark.asyncio
async def test_get_project_scorecard_missing_period(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_scorecard

    result = await get_project_scorecard(db_session, project_scored.id, year=2025, month=6)
    assert "error" in result


@pytest.mark.asyncio
async def test_get_project_scorecard_not_found(db_session: AsyncSession) -> None:
    from mcp_server.data.scorecard import get_project_scorecard

    result = await get_project_scorecard(db_session, uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_project_scorecard_includes_evm(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_scorecard

    result = await get_project_scorecard(db_session, project_scored.id)
    assert "evm" in result
    assert result["evm"]["budget_total"] == 100000.0
    assert result["evm"]["cost_to_date"] == 50000.0


# ---- get_project_history ----

@pytest.mark.asyncio
async def test_get_project_history(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_history

    result = await get_project_history(db_session, project_scored.id)
    assert result is not None
    assert len(result) == 2
    # Newest first
    assert result[0]["period"] == "2026-02"
    assert result[1]["period"] == "2026-01"
    assert result[0]["score"] is not None
    assert "dimensions" in result[0]


@pytest.mark.asyncio
async def test_get_project_history_includes_key_indicators(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_history

    result = await get_project_history(db_session, project_scored.id)
    # At least some entries should have key_indicators
    has_indicators = any("key_indicators" in entry for entry in result)
    assert has_indicators


@pytest.mark.asyncio
async def test_get_project_history_not_found(db_session: AsyncSession) -> None:
    from mcp_server.data.scorecard import get_project_history

    result = await get_project_history(db_session, uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_project_history_respects_limit(
    db_session: AsyncSession,
    project_scored: ProjectDB,
    seed_metrics,
) -> None:
    from mcp_server.data.scorecard import get_project_history

    result = await get_project_history(db_session, project_scored.id, limit=1)
    assert len(result) == 1
    assert result[0]["period"] == "2026-02"


# ---- get_global_metrics ----

@pytest_asyncio.fixture
async def seed_global_metrics(db_session: AsyncSession) -> list[GlobalMetricsDB]:
    jan = GlobalMetricsDB(
        period_year=2026,
        period_month=1,
        project_count=10,
        score=72.5,
        score_count=10,
        p_time=80.0,
        p_time_count=8,
        p_cost=65.0,
        p_cost_count=7,
        p_quality=70.0,
        p_quality_count=10,
        spi=0.85,
        spi_count=8,
        cpi=0.90,
        cpi_count=7,
        lead_time_days=0.75,
        lead_time_days_count=6,
    )
    feb = GlobalMetricsDB(
        period_year=2026,
        period_month=2,
        project_count=12,
        score=75.0,
        score_count=12,
        p_time=82.0,
        p_time_count=10,
        p_cost=68.0,
        p_cost_count=9,
        spi=0.88,
        spi_count=10,
    )
    db_session.add_all([jan, feb])
    await db_session.commit()
    return [jan, feb]


@pytest.mark.asyncio
async def test_get_global_metrics(
    db_session: AsyncSession,
    seed_global_metrics,
) -> None:
    from mcp_server.data.scorecard import get_global_metrics

    result = await get_global_metrics(db_session)
    assert len(result) == 2
    # Newest first
    assert result[0]["period"] == "2026-02"
    assert result[0]["project_count"] == 12
    assert "score" in result[0]["scores"]
    assert result[0]["scores"]["score"]["value"] == 75.0
    assert result[0]["scores"]["score"]["projects"] == 12


@pytest.mark.asyncio
async def test_get_global_metrics_includes_indicators(
    db_session: AsyncSession,
    seed_global_metrics,
) -> None:
    from mcp_server.data.scorecard import get_global_metrics

    result = await get_global_metrics(db_session)
    jan = result[1]
    assert "spi" in jan["indicators"]
    assert jan["indicators"]["spi"]["value"] == 0.85
    assert jan["indicators"]["spi"]["projects"] == 8


@pytest.mark.asyncio
async def test_get_global_metrics_respects_limit(
    db_session: AsyncSession,
    seed_global_metrics,
) -> None:
    from mcp_server.data.scorecard import get_global_metrics

    result = await get_global_metrics(db_session, limit=1)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_global_metrics_empty(db_session: AsyncSession) -> None:
    from mcp_server.data.scorecard import get_global_metrics

    result = await get_global_metrics(db_session)
    assert result == []
