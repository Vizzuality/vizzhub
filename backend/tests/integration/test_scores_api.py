"""Scores API integration tests."""

import pytest
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import MetricsDB
from app.models.project import ProjectDB


class TestScoresAPIIntegration:
    """Test the scores API endpoint with real data flow."""

    @pytest.mark.asyncio
    async def test_scores_endpoint_returns_valid_dimensions(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        """Verify scores endpoint calculates all dimensions correctly."""
        project, metrics = test_project_with_metrics

        response = await client.get(f"/api/scores/project/{project.id}")

        assert response.status_code == 200
        data = response.json()

        # Verify all dimensions are calculated (not null)
        dimensions = data["scores"]["dimensions"]
        assert dimensions["p_time"] is not None, "P_time should be calculated with EVM data"
        assert dimensions["p_cost"] is not None, "P_cost should be calculated with EVM data"
        assert dimensions["p_quality"] is not None, "P_quality should be calculated"
        assert dimensions["p_flow"] is not None, "P_flow should be calculated"
        assert dimensions["p_engineering"] is not None, "P_engineering should be calculated"
        assert dimensions["p_risk"] is not None, "P_risk should be calculated"
        assert dimensions["p_satisfaction"] is not None, "P_satisfaction should be calculated"

    @pytest.mark.asyncio
    async def test_scores_endpoint_uses_config_from_db(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        """Verify scores are calculated using config weights from database."""
        project, _ = test_project_with_metrics

        response = await client.get(f"/api/scores/project/{project.id}")
        assert response.status_code == 200

        data = response.json()
        weights = data["scores"]["weights_applied"]

        # Weights should sum to ~1.0 (with redistribution for missing dimensions)
        total_weight = sum(weights.values())
        assert 0.99 <= total_weight <= 1.01, f"Weights should sum to 1.0, got {total_weight}"

    @pytest.mark.asyncio
    async def test_scores_endpoint_returns_404_for_missing_project(
        self, client: AsyncClient
    ) -> None:
        """Verify 404 for non-existent project."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/scores/project/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_scores_endpoint_returns_error_for_project_without_metrics(
        self, client: AsyncClient, test_project: ProjectDB
    ) -> None:
        """Verify appropriate error when project has no metrics."""
        response = await client.get(f"/api/scores/project/{test_project.id}")
        assert response.status_code == 404
