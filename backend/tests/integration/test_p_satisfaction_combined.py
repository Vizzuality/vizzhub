"""Integration tests for P_satisfaction combined calculation.

Tests verify P_satisfaction calculation with both PM and client satisfaction.
"""

import pytest
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB


class TestPSatisfactionCombinedCalculation:
    """Test P_satisfaction calculation with both PM and client satisfaction."""

    @pytest.mark.asyncio
    async def test_pm_satisfaction_only(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify P_satisfaction uses only PM when client_survey is absent."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "pm_satisfaction": {
                    "delivery_complaints": "no",
                    "design_complaints": "no",
                    "overall_estimation": 5,
                },
            },
        )
        assert response.status_code == 201

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # PM satisfaction should be calculated
        assert indicators.get("pm_satisfaction") is not None
        # Client satisfaction should be None
        assert indicators.get("client_satisfaction") is None

    @pytest.mark.asyncio
    async def test_both_pm_and_client_satisfaction(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify P_satisfaction combines both when client_survey exists."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "pm_satisfaction": {
                    "delivery_complaints": "no",
                    "design_complaints": "no",
                    "overall_estimation": 5,
                },
                "client_survey": {
                    "understanding": 5,
                    "proactivity": 5,
                    "communication": 5,
                    "delivery_time": 5,
                    "response_time": 5,
                    "quality": 5,
                    "expectations": 5,
                    "recommend": 5,
                },
            },
        )
        assert response.status_code == 201

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # Both should be present
        assert indicators.get("pm_satisfaction") is not None
        assert indicators.get("client_satisfaction") is not None

        # P_satisfaction score should be high
        dimensions = data["scores"]["dimensions"]
        assert dimensions["p_satisfaction"] is not None
        assert dimensions["p_satisfaction"] >= 90  # Should be high with perfect scores
