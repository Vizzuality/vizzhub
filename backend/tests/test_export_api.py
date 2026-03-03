"""Tests for export API endpoints."""

import pytest
import pytest_asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.models.metrics import MetricsDB
from app.core.models.project import ProjectDB


@pytest_asyncio.fixture
async def export_project(db_session: AsyncSession) -> ProjectDB:
    """Create a project with metrics for export tests."""
    project = ProjectDB(
        id=str(uuid4()),
        name="API Export Test",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        status="in_progress",
    )
    db_session.add(project)
    await db_session.flush()

    metrics = MetricsDB(
        project_id=str(project.id),
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
        period_year=2025,
        period_month=1,
        snapshot_type="cumulative",
        budget_total=Decimal("100000"),
        cost_to_date=Decimal("45000"),
        percent_completed=Decimal("0.5"),
        percent_planned=Decimal("0.5"),
        bugs_total=5,
        tasks_completed=100,
        governance_exceptions=0,
        sev1_incident=False,
    )
    db_session.add(metrics)
    await db_session.commit()
    await db_session.refresh(project)
    return project


class TestProjectExportEndpoint:
    @pytest.mark.asyncio
    async def test_returns_xlsx(self, client: AsyncClient, export_project: ProjectDB):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={"start": "2025-01", "end": "2025-01"},
        )
        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in response.headers.get("content-disposition", "")

    @pytest.mark.asyncio
    async def test_includes_filename(
        self, client: AsyncClient, export_project: ProjectDB
    ):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={"start": "2025-01", "end": "2025-03"},
        )
        assert response.status_code == 200
        disposition = response.headers.get("content-disposition", "")
        assert "API_Export_Test" in disposition

    @pytest.mark.asyncio
    async def test_invalid_project_returns_404(self, client: AsyncClient):
        fake_id = str(uuid4())
        response = await client.get(
            f"/api/exports/project/{fake_id}",
            params={"start": "2025-01", "end": "2025-03"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_snapshot_type_parameter(
        self, client: AsyncClient, export_project: ProjectDB
    ):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={
                "start": "2025-01",
                "end": "2025-01",
                "snapshot_type": "punctual",
            },
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_date_format_returns_400(
        self, client: AsyncClient, export_project: ProjectDB
    ):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={"start": "2025-1", "end": "2025-03"},
        )
        assert response.status_code == 400


    @pytest.mark.asyncio
    async def test_end_before_start_returns_400(
        self, client: AsyncClient, export_project: ProjectDB
    ):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={"start": "2025-06", "end": "2025-01"},
        )
        assert response.status_code == 400
        assert "before" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_range_exceeds_max_returns_400(
        self, client: AsyncClient, export_project: ProjectDB
    ):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={"start": "2020-01", "end": "2025-12"},
        )
        assert response.status_code == 400
        assert "60" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_snapshot_type_returns_error(
        self, client: AsyncClient, export_project: ProjectDB
    ):
        response = await client.get(
            f"/api/exports/project/{export_project.id}",
            params={"start": "2025-01", "end": "2025-01", "snapshot_type": "invalid"},
        )
        assert response.status_code in (400, 422)


class TestGlobalExportEndpoint:
    @pytest.mark.asyncio
    async def test_returns_xlsx(
        self, client: AsyncClient, export_project: ProjectDB
    ):
        response = await client.get(
            "/api/exports/global",
            params={"start": "2025-01", "end": "2025-03"},
        )
        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @pytest.mark.asyncio
    async def test_returns_xlsx_even_with_no_projects(self, client: AsyncClient):
        response = await client.get(
            "/api/exports/global",
            params={"start": "2025-01", "end": "2025-01"},
        )
        assert response.status_code == 200
