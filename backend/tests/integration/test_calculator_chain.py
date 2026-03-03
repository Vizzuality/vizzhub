"""Integration tests for calculator chain.

Tests that all 8 dimension calculators work together correctly.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.modules.scorecard.models.metrics import MetricsDB
from app.core.models.project import ProjectDB


class TestCalculatorChainIntegration:
    """Test all 8 calculators work together correctly."""

    @pytest.mark.asyncio
    async def test_all_dimensions_calculate_with_complete_metrics(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        """Verify all 8 dimensions are calculated when metrics are complete."""
        project, _ = test_project_with_metrics

        response = await client.get(f"/api/scores/project/{project.id}")
        assert response.status_code == 200

        data = response.json()
        dimensions = data["scores"]["dimensions"]

        # All 8 dimensions should be present (though some may be null if data missing)
        expected_dimensions = [
            "p_time", "p_cost", "p_quality", "p_value",
            "p_satisfaction", "p_flow", "p_engineering", "p_risk"
        ]
        for dim in expected_dimensions:
            assert dim in dimensions, f"Missing dimension: {dim}"

    @pytest.mark.asyncio
    async def test_missing_metrics_dont_crash_other_dimensions(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify partial metrics don't prevent other dimensions from calculating."""
        # Create metrics with only EVM data (no GitHub, no Jira defects)
        today = date.today()
        metrics = MetricsDB(
            project_id=str(test_project.id),
            period_start=today - timedelta(days=30),
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="cumulative",
            budget_total=Decimal("100000.0"),
            cost_to_date=Decimal("50000.0"),
            percent_completed=Decimal("0.5"),
            percent_planned=Decimal("0.5"),
        )
        db_session.add(metrics)
        await db_session.commit()

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        dimensions = data["scores"]["dimensions"]

        # P_time and P_cost should be calculated from EVM data
        assert dimensions["p_time"] is not None
        assert dimensions["p_cost"] is not None

        # Other dimensions may be null but shouldn't crash
        assert "p_quality" in dimensions
        assert "p_flow" in dimensions

    @pytest.mark.asyncio
    async def test_final_score_uses_weighted_average(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
        scoring_config: ScoringConfig,
    ) -> None:
        """Verify final score is weighted average of dimension scores."""
        project, _ = test_project_with_metrics

        response = await client.get(f"/api/scores/project/{project.id}")
        assert response.status_code == 200

        data = response.json()
        final_score = data["scores"]["score"]
        dimensions = data["scores"]["dimensions"]
        weights = data["scores"]["weights_applied"]

        # Calculate expected weighted average
        expected = 0.0
        for dim, weight in weights.items():
            dim_key = f"p_{dim}"
            if dimensions.get(dim_key) is not None:
                expected += dimensions[dim_key] * weight

        assert abs(final_score - expected) < 1, f"Final score {final_score} doesn't match weighted average {expected}"
