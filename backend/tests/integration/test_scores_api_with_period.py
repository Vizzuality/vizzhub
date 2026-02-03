"""Integration tests for scores API with period parameters."""

import pytest
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import MetricsDB
from app.models.project import ProjectDB


class TestScoresAPIWithPeriod:
    """Test scores API with period parameters."""

    @pytest.mark.asyncio
    async def test_get_scores_with_year_month(
        self, client: AsyncClient, test_project_with_metrics: tuple
    ) -> None:
        """Should return scores for specific year/month."""
        project, metrics = test_project_with_metrics
        year = metrics.period_year
        month = metrics.period_month

        response = await client.get(
            f"/api/scores/project/{project.id}",
            params={"year": year, "month": month},
        )
        assert response.status_code == 200
        data = response.json()
        assert "indicators" in data
        assert "scores" in data

    @pytest.mark.asyncio
    async def test_get_scores_with_nonexistent_period(
        self, client: AsyncClient, test_project: ProjectDB
    ) -> None:
        """Should return 404 for period with no metrics."""
        response = await client.get(
            f"/api/scores/project/{test_project.id}",
            params={"year": 2020, "month": 1},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_scores_filters_by_period(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Should return 404 when querying a period without metrics even if other periods exist."""
        metrics_jan = MetricsDB(
            project_id=str(test_project.id),
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type="cumulative",
            budget_total=Decimal("100000.0"),
            cost_to_date=Decimal("50000.0"),
            percent_completed=Decimal("0.5"),
            percent_planned=Decimal("0.5"),
        )
        db_session.add(metrics_jan)
        await db_session.commit()

        response = await client.get(
            f"/api/scores/project/{test_project.id}",
            params={"year": 2024, "month": 1},
        )
        assert response.status_code == 200

        response = await client.get(
            f"/api/scores/project/{test_project.id}",
            params={"year": 2024, "month": 2},
        )
        assert response.status_code == 404
