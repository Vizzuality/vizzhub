"""Tests for budget line CRUD endpoints."""

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def setup_budget(db_session: AsyncSession) -> dict:
    """Create test data: user, project, functional areas."""
    user = UserDB(
        id=DEBUG_USER_ID,
        email="test@example.com",
        name="Test User",
    )
    db_session.add(user)
    await db_session.flush()

    project = ProjectDB(name="Test Project", status="live")
    db_session.add(project)
    await db_session.flush()

    fa_backend = FunctionalAreaDB(name="Backend Developer")
    fa_design = FunctionalAreaDB(name="Designer")
    fa_pm = FunctionalAreaDB(name="Project Manager")
    db_session.add_all([fa_backend, fa_design, fa_pm])
    await db_session.commit()

    await db_session.refresh(user)
    await db_session.refresh(project)
    await db_session.refresh(fa_backend)
    await db_session.refresh(fa_design)
    await db_session.refresh(fa_pm)

    return {
        "user": user,
        "project": project,
        "fa_backend": fa_backend,
        "fa_design": fa_design,
        "fa_pm": fa_pm,
    }


class TestBudgetLines:
    @pytest.mark.asyncio
    async def test_get_empty_budget_lines(
        self, client: AsyncClient, setup_budget: dict,
    ):
        project_id = str(setup_budget["project"].id)
        resp = await client.get(
            f"/api/tracker/projects/{project_id}/budget-lines",
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_put_creates_budget_lines(
        self, client: AsyncClient, setup_budget: dict,
    ):
        project_id = str(setup_budget["project"].id)
        fa_backend_id = str(setup_budget["fa_backend"].id)
        fa_design_id = str(setup_budget["fa_design"].id)

        resp = await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={
                "lines": [
                    {"functional_area_id": fa_backend_id, "days": 60},
                    {"functional_area_id": fa_design_id, "days": 40},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        backend_line = next(
            l for l in data if l["functional_area_id"] == fa_backend_id
        )
        design_line = next(
            l for l in data if l["functional_area_id"] == fa_design_id
        )

        assert backend_line["days"] == 60
        assert backend_line["functional_area_name"] == "Backend Developer"
        assert backend_line["percentage"] == pytest.approx(60.0)

        assert design_line["days"] == 40
        assert design_line["functional_area_name"] == "Designer"
        assert design_line["percentage"] == pytest.approx(40.0)

    @pytest.mark.asyncio
    async def test_put_replaces_existing_lines(
        self, client: AsyncClient, setup_budget: dict,
    ):
        project_id = str(setup_budget["project"].id)
        fa_backend_id = str(setup_budget["fa_backend"].id)
        fa_pm_id = str(setup_budget["fa_pm"].id)

        await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={
                "lines": [
                    {"functional_area_id": fa_backend_id, "days": 100},
                ],
            },
        )

        resp = await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={
                "lines": [
                    {"functional_area_id": fa_pm_id, "days": 30},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["functional_area_name"] == "Project Manager"
        assert data[0]["days"] == 30
        assert data[0]["percentage"] == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_put_validates_days_non_negative(
        self, client: AsyncClient, setup_budget: dict,
    ):
        project_id = str(setup_budget["project"].id)
        resp = await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={
                "lines": [
                    {"functional_area_id": None, "days": -5, "details": "Bad"},
                ],
            },
        )
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_line_without_functional_area_uses_details(
        self, client: AsyncClient, setup_budget: dict,
    ):
        project_id = str(setup_budget["project"].id)
        resp = await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={
                "lines": [
                    {"days": 20, "details": "Miscellaneous tasks"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["functional_area_id"] is None
        assert data[0]["functional_area_name"] is None
        assert data[0]["details"] == "Miscellaneous tasks"
        assert data[0]["percentage"] == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_percentage_calculation_correct(
        self, client: AsyncClient, setup_budget: dict,
    ):
        """3 lines: 10 + 20 + 70 = 100 total days."""
        project_id = str(setup_budget["project"].id)
        fa_backend_id = str(setup_budget["fa_backend"].id)
        fa_design_id = str(setup_budget["fa_design"].id)
        fa_pm_id = str(setup_budget["fa_pm"].id)

        resp = await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={
                "lines": [
                    {"functional_area_id": fa_backend_id, "days": 70},
                    {"functional_area_id": fa_design_id, "days": 20},
                    {"functional_area_id": fa_pm_id, "days": 10},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

        pct_map = {l["functional_area_name"]: l["percentage"] for l in data}
        assert pct_map["Backend Developer"] == pytest.approx(70.0)
        assert pct_map["Designer"] == pytest.approx(20.0)
        assert pct_map["Project Manager"] == pytest.approx(10.0)

    @pytest.mark.asyncio
    async def test_get_after_put_returns_joined_data(
        self, client: AsyncClient, setup_budget: dict,
    ):
        project_id = str(setup_budget["project"].id)
        fa_backend_id = str(setup_budget["fa_backend"].id)

        await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={
                "lines": [
                    {"functional_area_id": fa_backend_id, "days": 50},
                    {"days": 50, "details": "Other work"},
                ],
            },
        )

        resp = await client.get(
            f"/api/tracker/projects/{project_id}/budget-lines",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        named_line = next(l for l in data if l["functional_area_id"] is not None)
        assert named_line["functional_area_name"] == "Backend Developer"
        assert named_line["days"] == 50
        assert named_line["percentage"] == pytest.approx(50.0)

        unnamed_line = next(l for l in data if l["functional_area_id"] is None)
        assert unnamed_line["details"] == "Other work"
        assert unnamed_line["percentage"] == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_put_empty_lines_clears_budget(
        self, client: AsyncClient, setup_budget: dict,
    ):
        project_id = str(setup_budget["project"].id)
        fa_backend_id = str(setup_budget["fa_backend"].id)

        await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={
                "lines": [
                    {"functional_area_id": fa_backend_id, "days": 50},
                ],
            },
        )

        resp = await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={"lines": []},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_zero_days_get_null_percentage(
        self, client: AsyncClient, setup_budget: dict,
    ):
        """When all lines have 0 days, percentage should be null."""
        project_id = str(setup_budget["project"].id)
        resp = await client.put(
            f"/api/tracker/projects/{project_id}/budget-lines",
            json={
                "lines": [
                    {"days": 0, "details": "Placeholder"},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["percentage"] is None


class TestFunctionalAreas:
    @pytest.mark.asyncio
    async def test_list_functional_areas(
        self, client: AsyncClient, setup_budget: dict,
    ):
        resp = await client.get("/api/functional-areas")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        names = [fa["name"] for fa in data]
        assert names == ["Backend Developer", "Designer", "Project Manager"]
