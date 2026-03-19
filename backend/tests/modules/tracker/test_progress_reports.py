"""Tests for progress report CRUD endpoints."""

from datetime import date
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def setup_progress(db_session: AsyncSession) -> dict:
    """Create test data: user, project, two reporting periods."""
    user = UserDB(id=DEBUG_USER_ID, email="test@example.com", name="Test User")
    db_session.add(user)
    await db_session.flush()

    project = ProjectDB(name="Test Project", status="live")
    db_session.add(project)
    await db_session.flush()

    period_jan = ReportingPeriodDB(date=date(2026, 1, 1), base_rate=175, status="finished")
    period_feb = ReportingPeriodDB(date=date(2026, 2, 1), base_rate=175, status="active")
    db_session.add_all([period_jan, period_feb])
    await db_session.commit()

    await db_session.refresh(project)
    await db_session.refresh(period_jan)
    await db_session.refresh(period_feb)

    return {
        "project_id": str(project.id),
        "period_jan_id": str(period_jan.id),
        "period_feb_id": str(period_feb.id),
    }


@pytest.mark.asyncio
class TestProgressReports:
    async def test_list_empty(
        self, client: AsyncClient, setup_progress: dict,
    ) -> None:
        pid = setup_progress["project_id"]
        resp = await client.get(f"/api/tracker/projects/{pid}/progress")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_first_progress(
        self, client: AsyncClient, setup_progress: dict,
    ) -> None:
        pid = setup_progress["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_jan_id"],
                "percentage": 30,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["percentage"] == 30.0
        assert data["delta"] == 30.0
        assert data["period_date"] == "2026-01-01"

    async def test_create_second_progress_calculates_delta(
        self, client: AsyncClient, setup_progress: dict,
    ) -> None:
        pid = setup_progress["project_id"]
        # First: Jan at 30%
        await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_jan_id"],
                "percentage": 30,
            },
        )
        # Second: Feb at 55%
        resp = await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_feb_id"],
                "percentage": 55,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["percentage"] == 55.0
        assert data["delta"] == 25.0

    async def test_duplicate_returns_409(
        self, client: AsyncClient, setup_progress: dict,
    ) -> None:
        pid = setup_progress["project_id"]
        await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_jan_id"],
                "percentage": 30,
            },
        )
        resp = await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_jan_id"],
                "percentage": 40,
            },
        )
        assert resp.status_code == 409

    async def test_update_progress(
        self, client: AsyncClient, setup_progress: dict,
    ) -> None:
        pid = setup_progress["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_jan_id"],
                "percentage": 30,
            },
        )
        progress_id = resp.json()["id"]

        resp = await client.put(
            f"/api/tracker/projects/{pid}/progress/{progress_id}",
            json={"percentage": 45},
        )
        assert resp.status_code == 200
        assert resp.json()["percentage"] == 45.0
        assert resp.json()["delta"] == 45.0

    async def test_delete_progress(
        self, client: AsyncClient, setup_progress: dict,
    ) -> None:
        pid = setup_progress["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_jan_id"],
                "percentage": 30,
            },
        )
        progress_id = resp.json()["id"]

        resp = await client.delete(
            f"/api/tracker/projects/{pid}/progress/{progress_id}",
        )
        assert resp.status_code == 204

        resp = await client.get(f"/api/tracker/projects/{pid}/progress")
        assert resp.json() == []

    async def test_list_ordered_by_date(
        self, client: AsyncClient, setup_progress: dict,
    ) -> None:
        pid = setup_progress["project_id"]
        # Create Feb first, then Jan
        await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_feb_id"],
                "percentage": 55,
            },
        )
        await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_jan_id"],
                "percentage": 30,
            },
        )
        resp = await client.get(f"/api/tracker/projects/{pid}/progress")
        data = resp.json()
        assert len(data) == 2
        assert data[0]["period_date"] == "2026-01-01"
        assert data[1]["period_date"] == "2026-02-01"

    async def test_batch_progress(
        self, client: AsyncClient, setup_progress: dict,
    ) -> None:
        pid = setup_progress["project_id"]
        await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_jan_id"],
                "percentage": 30,
            },
        )
        await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_feb_id"],
                "percentage": 55,
            },
        )
        resp = await client.post(
            "/api/tracker/projects/batch-progress",
            json={"project_ids": [pid]},
        )
        assert resp.status_code == 200
        data = resp.json()["progress"]
        assert pid in data
        assert data[pid]["percentage"] == 55.0
        assert data[pid]["delta"] == 25.0

    async def test_percentage_validation(
        self, client: AsyncClient, setup_progress: dict,
    ) -> None:
        pid = setup_progress["project_id"]
        resp = await client.post(
            f"/api/tracker/projects/{pid}/progress",
            json={
                "reporting_period_id": setup_progress["period_jan_id"],
                "percentage": 101,
            },
        )
        assert resp.status_code == 400
