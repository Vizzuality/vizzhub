"""Tests for Jobs API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


class TestJobsAPI:
    """Tests for Jobs API endpoints."""

    @pytest.mark.asyncio
    async def test_list_jobs_returns_empty_list(self, client: AsyncClient) -> None:
        """List jobs returns empty list when no jobs exist."""
        response = await client.get("/api/jobs")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_capture_history_job_success(
        self, client: AsyncClient
    ) -> None:
        """Create capture history job successfully enqueues to ARQ."""
        project_response = await client.post(
            "/api/scorecards",
            json={
                "name": "Test Project",
                "jira_project_key": "TEST",
                "github_repo": "org/repo",
            },
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        mock_arq_job = MagicMock()
        mock_arq_job.job_id = "arq-job-123"

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=mock_arq_job)
        mock_pool.close = AsyncMock()

        with patch("app.api.jobs.get_redis_pool", return_value=mock_pool):
            response = await client.post(
                "/api/jobs/capture-history",
                json={
                    "project_id": project_id,
                    "from_year": 2024,
                    "from_month": 1,
                    "to_year": 2024,
                    "to_month": 3,
                    "force": True,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "capture_history"
        assert data["status"] == "pending"
        assert "Historical Capture" in data["name"]
        assert data["progress"] == 0

    @pytest.mark.asyncio
    async def test_create_capture_history_job_invalid_date_range(
        self, client: AsyncClient
    ) -> None:
        """Create capture history job fails with invalid date range."""
        project_response = await client.post(
            "/api/scorecards",
            json={"name": "Test Project"},
        )
        project_id = project_response.json()["id"]

        response = await client.post(
            "/api/jobs/capture-history",
            json={
                "project_id": project_id,
                "from_year": 2024,
                "from_month": 6,
                "to_year": 2024,
                "to_month": 3,
                "force": True,
            },
        )

        assert response.status_code == 400
        assert "End date must be after start date" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, client: AsyncClient) -> None:
        """Get job returns 404 for non-existent job."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/jobs/{fake_uuid}")
        assert response.status_code == 404
        assert "Job not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_job_success(self, client: AsyncClient) -> None:
        """Get job returns job details."""
        project_response = await client.post(
            "/api/scorecards",
            json={"name": "Test Project"},
        )
        project_id = project_response.json()["id"]

        mock_arq_job = MagicMock()
        mock_arq_job.job_id = "arq-job-456"

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=mock_arq_job)
        mock_pool.close = AsyncMock()

        with patch("app.api.jobs.get_redis_pool", return_value=mock_pool):
            create_response = await client.post(
                "/api/jobs/capture-history",
                json={
                    "project_id": project_id,
                    "from_year": 2024,
                    "from_month": 1,
                    "to_year": 2024,
                    "to_month": 1,
                    "force": True,
                },
            )

        job_id = create_response.json()["id"]

        response = await client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["type"] == "capture_history"
        assert data["params"]["from_year"] == 2024
        assert data["params"]["from_month"] == 1
