"""Tests for non-staff cost CRUD endpoints."""

import datetime as dt
from decimal import Decimal
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
async def setup_costs(db_session: AsyncSession) -> dict:
    """Create test data: user, period, project."""
    user = UserDB(
        id=DEBUG_USER_ID,
        email="test@example.com",
        name="Test User",
    )
    db_session.add(user)
    await db_session.flush()

    period = ReportingPeriodDB(
        date=dt.date(2026, 3, 1), base_rate=Decimal("175"), status="active",
    )
    db_session.add(period)
    await db_session.flush()

    project = ProjectDB(name="Test Project", status="live")
    db_session.add(project)
    await db_session.commit()

    await db_session.refresh(user)
    await db_session.refresh(period)
    await db_session.refresh(project)

    return {
        "user": user,
        "period": period,
        "project": project,
    }


class TestNonStaffCostsCRUD:
    @pytest.mark.asyncio
    async def test_create_non_staff_cost(
        self, client: AsyncClient, setup_costs: dict,
    ):
        resp = await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": str(setup_costs["project"].id),
                "reporting_period_id": str(setup_costs["period"].id),
                "cost": 1500.00,
                "cost_type": "outsource",
                "details": "External contractor",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["cost"] == pytest.approx(1500)
        assert data["cost_type"] == "outsource"
        assert data["details"] == "External contractor"
        assert data["project_id"] == str(setup_costs["project"].id)
        assert data["reporting_period_id"] == str(setup_costs["period"].id)

    @pytest.mark.asyncio
    async def test_list_by_project(
        self, client: AsyncClient, setup_costs: dict,
    ):
        await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": str(setup_costs["project"].id),
                "reporting_period_id": str(setup_costs["period"].id),
                "cost": 500.00,
                "cost_type": "travel",
            },
        )
        resp = await client.get(
            "/api/tracker/non-staff-costs",
            params={"project_id": str(setup_costs["project"].id)},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_list_by_project_and_period(
        self, client: AsyncClient, setup_costs: dict, db_session: AsyncSession,
    ):
        period2 = ReportingPeriodDB(
            date=dt.date(2026, 4, 1), base_rate=Decimal("175"), status="active",
        )
        db_session.add(period2)
        await db_session.commit()
        await db_session.refresh(period2)

        project_id = str(setup_costs["project"].id)
        period1_id = str(setup_costs["period"].id)
        period2_id = str(period2.id)

        await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": project_id,
                "reporting_period_id": period1_id,
                "cost": 100.00,
                "cost_type": "servers",
            },
        )
        await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": project_id,
                "reporting_period_id": period2_id,
                "cost": 200.00,
                "cost_type": "others",
            },
        )

        resp = await client.get(
            "/api/tracker/non-staff-costs",
            params={
                "project_id": project_id,
                "reporting_period_id": period1_id,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["cost"] == pytest.approx(100)

    @pytest.mark.asyncio
    async def test_list_requires_project_id(
        self, client: AsyncClient, setup_costs: dict,
    ):
        resp = await client.get("/api/tracker/non-staff-costs")
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_update_non_staff_cost(
        self, client: AsyncClient, setup_costs: dict,
    ):
        create_resp = await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": str(setup_costs["project"].id),
                "reporting_period_id": str(setup_costs["period"].id),
                "cost": 1000.00,
                "cost_type": "outsource",
            },
        )
        cost_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/tracker/non-staff-costs/{cost_id}",
            json={"cost": 2000.00, "cost_type": "travel"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cost"] == pytest.approx(2000)
        assert data["cost_type"] == "travel"

    @pytest.mark.asyncio
    async def test_delete_non_staff_cost(
        self, client: AsyncClient, setup_costs: dict,
    ):
        create_resp = await client.post(
            "/api/tracker/non-staff-costs",
            json={
                "project_id": str(setup_costs["project"].id),
                "reporting_period_id": str(setup_costs["period"].id),
                "cost": 300.00,
                "cost_type": "servers",
            },
        )
        cost_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/tracker/non-staff-costs/{cost_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/tracker/non-staff-costs/{cost_id}")
        assert resp.status_code == 404
