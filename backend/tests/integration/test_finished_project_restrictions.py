"""Integration tests for finished project metrics restrictions.

Tests verify that finished projects only allow end-of-project metrics
(strategic_impact, client_survey) and block regular metric updates.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB


class TestFinishedProjectMetricsRestrictions:
    """Test that finished projects only allow end-of-project metrics."""

    @pytest_asyncio.fixture
    async def finished_project(self, db_session: AsyncSession) -> ProjectDB:
        """Create a finished project."""
        project = ProjectDB(
            id=str(uuid4()),
            name="Finished Integration Project",
            jira_project_key="FIP",
            github_repo="test/finished-project",
            start_date=date.today() - timedelta(days=180),
            end_date=date.today() - timedelta(days=30),
            status="finished",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)
        return project

    @pytest.mark.asyncio
    async def test_finished_project_allows_strategic_impact(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects allow strategic_impact updates."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "strategic_impact": "high",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["strategic_impact"] == "high"

    @pytest.mark.asyncio
    async def test_finished_project_allows_client_survey(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects allow client_survey updates."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "client_survey": {
                    "understanding": 4,
                    "proactivity": 4,
                    "communication": 5,
                    "delivery_time": 4,
                    "response_time": 4,
                    "quality": 5,
                    "expectations": 4,
                    "recommend": 5,
                },
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["client_survey"]["quality"] == 5

    @pytest.mark.asyncio
    async def test_finished_project_blocks_evm_data(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects block EVM data updates."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "evm_data": {
                    "budget_total": 100000.0,
                    "cost_to_date": 50000.0,
                    "percent_completed": 0.5,
                    "percent_planned": 0.5,
                },
            },
        )

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()
        assert "evm_data" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_finished_project_blocks_jira_defects(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects block Jira defect metrics."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "jira_defects": {
                    "bugs_total": 10,
                    "tasks_completed": 50,
                },
            },
        )

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_finished_project_blocks_github_metrics(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects block GitHub metrics."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "github_metrics": {
                    "total_merged_prs": 100,
                    "prs_without_review": 5,
                },
            },
        )

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_finished_project_blocks_governance_exceptions(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects block governance_exceptions updates."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "governance_exceptions": 2,
            },
        )

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_finished_project_allows_combined_end_of_project_metrics(
        self,
        client: AsyncClient,
        finished_project: ProjectDB,
    ) -> None:
        """Verify finished projects allow both strategic_impact and client_survey together."""
        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "strategic_impact": "transformational",
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
        data = response.json()
        assert data["strategic_impact"] == "transformational"
        assert data["client_survey"]["quality"] == 5

    @pytest.mark.asyncio
    async def test_reopen_project_allows_regular_metrics(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        finished_project: ProjectDB,
    ) -> None:
        """Verify reopening a project allows regular metrics again."""
        response = await client.patch(
            f"/api/projects/{finished_project.id}",
            json={"status": "live"},
        )
        assert response.status_code == 200

        response = await client.post(
            f"/api/metrics/project/{finished_project.id}",
            json={
                "period_start": str(date.today() - timedelta(days=30)),
                "period_end": str(date.today()),
                "governance_exceptions": 1,
            },
        )

        assert response.status_code == 201
