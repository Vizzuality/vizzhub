"""Integration tests for end-of-project metrics (strategic_impact, client_survey)."""

import pytest
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import ProjectDB


class TestEndOfProjectMetricsIntegration:
    """Test strategic_impact and client_survey end-of-project metrics."""

    @pytest.mark.asyncio
    async def test_strategic_impact_affects_p_value_score(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify strategic_impact is reflected in P_value calculation."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Create metrics with high strategic impact
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "strategic_impact": "transformational",
            },
        )
        assert response.status_code == 201

        # Get scores
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # OKR impact should reflect transformational = 1.0
        assert indicators.get("okr_impact") is not None
        assert indicators["okr_impact"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_strategic_impact_low_value(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify low strategic_impact produces lower score."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "strategic_impact": "low",
            },
        )
        assert response.status_code == 201

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # OKR impact should reflect low = 0.25
        assert indicators.get("okr_impact") == pytest.approx(0.25)

    @pytest.mark.asyncio
    async def test_client_survey_affects_p_satisfaction(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify client_survey data affects P_satisfaction calculation."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Create metrics with perfect client survey
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
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

        # Client satisfaction should be 1.0 (all 5s = 100%)
        assert indicators.get("client_satisfaction") is not None
        assert indicators["client_satisfaction"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_client_survey_weighted_average(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify client_survey uses weighted average calculation."""
        period_start = str(date.today() - timedelta(days=30))
        period_end = str(date.today())

        # Create metrics with mixed ratings
        # Quality has 24% weight, so rating of 5 there should have more impact
        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json={
                "period_start": period_start,
                "period_end": period_end,
                "client_survey": {
                    "understanding": 3,    # 12%
                    "proactivity": 3,      # 12%
                    "communication": 3,    # 10%
                    "delivery_time": 3,    # 14%
                    "response_time": 3,    # 10%
                    "quality": 5,          # 24% - highest weight
                    "expectations": 3,     # 12%
                    "recommend": 3,        # 6%
                },
            },
        )
        assert response.status_code == 201

        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        indicators = data["indicators"]

        # Should be higher than (3/5 = 0.6) due to quality weight
        client_sat = indicators.get("client_satisfaction")
        assert client_sat is not None
        assert client_sat > 0.6  # Must be above average due to high quality score
