"""Capture endpoint integration tests."""

import pytest
from datetime import date, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import MetricsDB
from app.models.project import ProjectDB


class TestCaptureEndpointIntegration:
    """Tests for the capture-period endpoint validation."""

    @pytest.mark.asyncio
    async def test_capture_requires_jira_or_github(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Verify 400 error when project has neither Jira nor GitHub."""
        project = ProjectDB(
            id=str(uuid4()),
            name="No Sources Project",
            jira_project_key=None,
            github_repo=None,
            start_date=date.today() - timedelta(days=90),
            status="in_progress",
        )
        db_session.add(project)
        await db_session.commit()

        response = await client.post(
            f"/api/scorecards/{project.id}/capture-period",
            json={"year": 2024, "month": 1},
        )
        assert response.status_code == 400
        assert "Jira or GitHub" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_capture_returns_409_when_period_exists(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Verify 409 error when period already captured without force."""
        today = date.today()

        # Create existing punctual snapshot
        existing = MetricsDB(
            project_id=str(test_project.id),
            period_start=date(today.year, today.month, 1),
            period_end=today,
            period_year=today.year,
            period_month=today.month,
            snapshot_type="punctual",
        )
        db_session.add(existing)
        await db_session.commit()

        response = await client.post(
            f"/api/scorecards/{test_project.id}/capture-period",
            json={"year": today.year, "month": today.month, "force": False},
        )
        assert response.status_code == 409
        assert "already captured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_capture_request_validation(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify request validation for year/month bounds."""
        # Invalid year (too old) - returns 400 with validation error
        response = await client.post(
            f"/api/scorecards/{test_project.id}/capture-period",
            json={"year": 2019, "month": 1},
        )
        assert response.status_code == 400
        # Verify it's a validation error by checking response contains the error
        response_text = str(response.json())
        assert "2020" in response_text or "year" in response_text.lower()

        # Invalid month (out of range)
        response = await client.post(
            f"/api/scorecards/{test_project.id}/capture-period",
            json={"year": 2024, "month": 13},
        )
        assert response.status_code == 400
        response_text = str(response.json())
        assert "12" in response_text or "month" in response_text.lower()

    @pytest.mark.asyncio
    async def test_capture_accepts_optional_year_month(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """Verify capture defaults to current month when year/month not provided.

        Note: This test will only validate request acceptance, not actual collection
        since that would require mocking external services.
        """
        project = ProjectDB(
            id=str(uuid4()),
            name="No Sources Project",
            jira_project_key=None,
            github_repo=None,
            start_date=date.today() - timedelta(days=90),
            status="in_progress",
        )
        db_session.add(project)
        await db_session.commit()

        # Empty body should be accepted (default to current month)
        # Will fail with 400 due to no sources, but that's a different error
        response = await client.post(
            f"/api/scorecards/{project.id}/capture-period",
            json={},
        )
        # Should get 400 for missing sources, not 422 for validation
        assert response.status_code == 400
        assert "Jira or GitHub" in response.json()["detail"]
