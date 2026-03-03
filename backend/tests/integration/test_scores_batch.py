"""Integration tests for POST /scores/batch endpoint."""

import pytest
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.models.metrics import MetricsDB
from app.core.models.project import ProjectDB


class TestScoresBatchEndpoint:
    """Test the batch scores endpoint."""

    @pytest.mark.asyncio
    async def test_batch_returns_scores_for_valid_projects(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        project, _ = test_project_with_metrics
        response = await client.post(
            "/api/scores/batch",
            json={"project_ids": [str(project.id)]},
        )

        assert response.status_code == 200
        data = response.json()
        assert str(project.id) in data["scores"]
        assert data["scores"][str(project.id)]["scores"]["score"] is not None
        assert data["errors"] == {}

    @pytest.mark.asyncio
    async def test_batch_returns_error_for_missing_metrics(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        response = await client.post(
            "/api/scores/batch",
            json={"project_ids": [str(test_project.id)]},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["scores"] == {}
        assert str(test_project.id) in data["errors"]
        assert "No metrics found" in data["errors"][str(test_project.id)]

    @pytest.mark.asyncio
    async def test_batch_mixed_valid_and_missing(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        project, _ = test_project_with_metrics
        missing_id = str(uuid4())

        response = await client.post(
            "/api/scores/batch",
            json={"project_ids": [str(project.id), missing_id]},
        )

        assert response.status_code == 200
        data = response.json()
        assert str(project.id) in data["scores"]
        assert missing_id in data["errors"]

    @pytest.mark.asyncio
    async def test_batch_empty_list_rejected(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.post(
            "/api/scores/batch",
            json={"project_ids": []},
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_default_snapshot_type_cumulative(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        project, _ = test_project_with_metrics
        response = await client.post(
            "/api/scores/batch",
            json={"project_ids": [str(project.id)]},
        )

        assert response.status_code == 200
        data = response.json()
        assert str(project.id) in data["scores"]

    @pytest.mark.asyncio
    async def test_batch_punctual_no_data(
        self,
        client: AsyncClient,
        test_project_with_metrics: tuple[ProjectDB, MetricsDB],
    ) -> None:
        project, _ = test_project_with_metrics
        response = await client.post(
            "/api/scores/batch",
            json={
                "project_ids": [str(project.id)],
                "snapshot_type": "punctual",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert str(project.id) in data["errors"]
