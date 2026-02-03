"""Collectors integration tests."""

import pytest
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import ProjectDB


class TestCollectorsIntegration:
    """Test collector flows create metrics that affect scores."""

    @pytest.mark.asyncio
    async def test_metrics_creation_affects_scores(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify that creating metrics changes the scores."""
        # First, no metrics should return 404
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 404

        # Create metrics via API
        metrics_data = {
            "period_start": str(date.today() - timedelta(days=30)),
            "period_end": str(date.today()),
            "evm_data": {
                "budget_total": 100000.0,
                "cost_to_date": 50000.0,
                "percent_completed": 0.5,
                "percent_planned": 0.5,
            },
            "governance_exceptions": 0,
        }

        response = await client.post(
            f"/api/metrics/project/{test_project.id}",
            json=metrics_data,
        )
        assert response.status_code == 201  # 201 Created for new resource

        # Now scores should be calculable
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["scores"]["dimensions"]["p_time"] is not None
        assert data["scores"]["dimensions"]["p_cost"] is not None
