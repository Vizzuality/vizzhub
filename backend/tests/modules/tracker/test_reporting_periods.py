"""Tests for reporting period endpoints."""

import datetime as dt

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracker.models.reporting_period import ReportingPeriodDB


@pytest_asyncio.fixture
async def period(db_session: AsyncSession) -> ReportingPeriodDB:
    """Create a test reporting period."""
    p = ReportingPeriodDB(
        date=dt.date(2026, 3, 1),
        base_rate=175.00,
        status="unstarted",
    )
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


class TestReportingPeriodsCRUD:
    @pytest.mark.asyncio
    async def test_create_period(self, client: AsyncClient):
        resp = await client.post(
            "/api/tracker/reporting-periods",
            json={"date": "2026-03-01"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["date"] == "2026-03-01"
        assert data["base_rate"] == 175.0
        assert data["status"] == "unstarted"

    @pytest.mark.asyncio
    async def test_create_period_custom_base_rate(self, client: AsyncClient):
        resp = await client.post(
            "/api/tracker/reporting-periods",
            json={"date": "2026-03-01", "base_rate": 190.0},
        )
        assert resp.status_code == 201
        assert resp.json()["base_rate"] == 190.0

    @pytest.mark.asyncio
    async def test_list_periods(self, client: AsyncClient, period: ReportingPeriodDB):
        resp = await client.get("/api/tracker/reporting-periods")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_period(self, client: AsyncClient, period: ReportingPeriodDB):
        resp = await client.get(f"/api/tracker/reporting-periods/{period.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(period.id)

    @pytest.mark.asyncio
    async def test_get_period_not_found(self, client: AsyncClient):
        resp = await client.get(
            "/api/tracker/reporting-periods/00000000-0000-0000-0000-000000000000",
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_period(self, client: AsyncClient, period: ReportingPeriodDB):
        resp = await client.put(
            f"/api/tracker/reporting-periods/{period.id}",
            json={"base_rate": 190.0},
        )
        assert resp.status_code == 200
        assert resp.json()["base_rate"] == 190.0

    @pytest.mark.asyncio
    async def test_delete_unstarted_period(
        self, client: AsyncClient, period: ReportingPeriodDB,
    ):
        resp = await client.delete(f"/api/tracker/reporting-periods/{period.id}")
        assert resp.status_code == 204


class TestReportingPeriodsStateMachine:
    @pytest.mark.asyncio
    async def test_activate_period(
        self, client: AsyncClient, period: ReportingPeriodDB,
    ):
        resp = await client.post(
            f"/api/tracker/reporting-periods/{period.id}/activate",
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_finish_active_period(
        self, client: AsyncClient, period: ReportingPeriodDB,
    ):
        await client.post(f"/api/tracker/reporting-periods/{period.id}/activate")
        resp = await client.post(
            f"/api/tracker/reporting-periods/{period.id}/finish",
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "finished"

    @pytest.mark.asyncio
    async def test_reactivate_finished_period(
        self, client: AsyncClient, period: ReportingPeriodDB,
    ):
        await client.post(f"/api/tracker/reporting-periods/{period.id}/activate")
        await client.post(f"/api/tracker/reporting-periods/{period.id}/finish")
        resp = await client.post(
            f"/api/tracker/reporting-periods/{period.id}/reactivate",
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_invalid_transition_unstarted_to_finished(
        self, client: AsyncClient, period: ReportingPeriodDB,
    ):
        resp = await client.post(
            f"/api/tracker/reporting-periods/{period.id}/finish",
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_single_active_constraint(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        p1 = ReportingPeriodDB(date=dt.date(2026, 1, 1), base_rate=175, status="unstarted")
        p2 = ReportingPeriodDB(date=dt.date(2026, 2, 1), base_rate=175, status="unstarted")
        db_session.add_all([p1, p2])
        await db_session.commit()
        await db_session.refresh(p1)
        await db_session.refresh(p2)

        await client.post(f"/api/tracker/reporting-periods/{p1.id}/activate")
        resp = await client.post(f"/api/tracker/reporting-periods/{p2.id}/activate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        check = await client.get(f"/api/tracker/reporting-periods/{p1.id}")
        assert check.json()["status"] == "finished"

    @pytest.mark.asyncio
    async def test_can_delete_active_period_without_reports(
        self, client: AsyncClient, period: ReportingPeriodDB,
    ):
        await client.post(f"/api/tracker/reporting-periods/{period.id}/activate")
        resp = await client.delete(f"/api/tracker/reporting-periods/{period.id}")
        assert resp.status_code == 204
