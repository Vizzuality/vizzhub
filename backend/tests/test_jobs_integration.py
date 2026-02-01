"""Integration tests for Jobs API."""
import pytest
import pytest_asyncio
from datetime import date, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.models.job import JobStatus, JobType
from app.models.project import ProjectDB


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession, scoring_config: ScoringConfig) -> ProjectDB:
    """Create a test project for jobs tests."""
    project = ProjectDB(
        id=str(uuid4()),
        name="Jobs Test Project",
        jira_project_key="JTP",
        github_repo="test/jobs-test",
        start_date=date.today() - timedelta(days=90),
        end_date=date.today() + timedelta(days=90),
        status="in_progress",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.mark.asyncio
async def test_create_capture_history_job(client: AsyncClient, test_project: ProjectDB) -> None:
    """Test creating a capture history job."""
    response = await client.post(
        "/api/jobs/capture-history",
        json={
            "project_id": str(test_project.id),
            "from_year": 2024,
            "from_month": 1,
            "to_year": 2024,
            "to_month": 3,
            "force": True,
        },
    )

    if response.status_code == 500:
        assert "Redis" in response.json()["detail"]
        return

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "capture_history"
    assert data["status"] == "pending"
    assert "Historical Capture" in data["name"]


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient) -> None:
    """Test getting non-existent job."""
    response = await client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs_empty(client: AsyncClient) -> None:
    """Test listing jobs when none exist."""
    response = await client.get("/api/jobs/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
