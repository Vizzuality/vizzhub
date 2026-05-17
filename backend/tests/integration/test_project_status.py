"""Integration tests for project status affecting collectors and metrics."""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB


class TestProjectStatusIntegration:
    """Test project status affects collectors and metrics."""

    @pytest.mark.asyncio
    async def test_finished_project_blocks_jira_collector(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Verify Jira collector is blocked for finished projects."""
        # Create finished project
        project = ProjectDB(
            id=str(uuid4()),
            name="Finished Project",
            jira_project_key="FIN",
            start_date=date.today() - timedelta(days=180),
            end_date=date.today() - timedelta(days=30),
            status="finished",
        )
        db_session.add(project)
        await db_session.commit()

        response = await client.post(f"/api/collect/project/{project.id}/jira")

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_finished_project_blocks_github_collector(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Verify GitHub collector is blocked for finished projects."""
        project = ProjectDB(
            id=str(uuid4()),
            name="Finished Project",
            github_repo="test/finished",
            start_date=date.today() - timedelta(days=180),
            end_date=date.today() - timedelta(days=30),
            status="finished",
        )
        db_session.add(project)
        await db_session.commit()

        response = await client.post(f"/api/collect/project/{project.id}/github")

        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_live_project_allows_collectors(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify collectors work for live projects (may fail for other reasons)."""
        # This will likely fail due to missing Jira/GitHub credentials,
        # but should NOT fail with "finished project" error
        response = await client.post(f"/api/collect/project/{test_project.id}/jira")

        # Should not be 400 with "finished" message
        if response.status_code == 400:
            assert "finished" not in response.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_project_status_change_affects_collectors(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify changing project status from live to finished blocks collectors."""
        # Update project to finished
        response = await client.patch(
            f"/api/projects/{test_project.id}",
            json={"status": "finished"},
        )
        assert response.status_code == 200

        # Now collectors should be blocked
        response = await client.post(f"/api/collect/project/{test_project.id}/jira")
        assert response.status_code == 400
        assert "finished" in response.json()["detail"].lower()
