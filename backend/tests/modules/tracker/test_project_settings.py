"""Tests for project tracker settings endpoints (contract_rate)."""

from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.tracker.models.project_settings import TrackerProjectSettingsDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture
async def project(db_session: AsyncSession) -> ProjectDB:
    p = ProjectDB(name="Settings Test Project", status="live")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest_asyncio.fixture
async def project_with_settings(
    db_session: AsyncSession, project: ProjectDB,
) -> ProjectDB:
    settings = TrackerProjectSettingsDB(
        project_id=project.id, contract_rate=Decimal("210.00"),
    )
    db_session.add(settings)
    await db_session.commit()
    return project


class TestGetProjectSettings:
    @pytest.mark.asyncio
    async def test_returns_default_when_no_settings(
        self, client: AsyncClient, project: ProjectDB,
    ) -> None:
        resp = await client.get(f"/api/tracker/projects/{project.id}/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_id"] == str(project.id)
        assert data["contract_rate"] == 175.0

    @pytest.mark.asyncio
    async def test_returns_existing_settings(
        self, client: AsyncClient, project_with_settings: ProjectDB,
    ) -> None:
        resp = await client.get(
            f"/api/tracker/projects/{project_with_settings.id}/settings"
        )
        assert resp.status_code == 200
        assert resp.json()["contract_rate"] == 210.0


class TestUpdateProjectSettings:
    @pytest.mark.asyncio
    async def test_creates_settings_when_none_exist(
        self, client: AsyncClient, project: ProjectDB,
    ) -> None:
        resp = await client.put(
            f"/api/tracker/projects/{project.id}/settings",
            json={"contract_rate": 200.0},
        )
        assert resp.status_code == 200
        assert resp.json()["contract_rate"] == 200.0

        resp2 = await client.get(f"/api/tracker/projects/{project.id}/settings")
        assert resp2.json()["contract_rate"] == 200.0

    @pytest.mark.asyncio
    async def test_updates_existing_settings(
        self, client: AsyncClient, project_with_settings: ProjectDB,
    ) -> None:
        resp = await client.put(
            f"/api/tracker/projects/{project_with_settings.id}/settings",
            json={"contract_rate": 190.5},
        )
        assert resp.status_code == 200
        assert resp.json()["contract_rate"] == 190.5

    @pytest.mark.asyncio
    async def test_rejects_zero_rate(
        self, client: AsyncClient, project: ProjectDB,
    ) -> None:
        resp = await client.put(
            f"/api/tracker/projects/{project.id}/settings",
            json={"contract_rate": 0},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_negative_rate(
        self, client: AsyncClient, project: ProjectDB,
    ) -> None:
        resp = await client.put(
            f"/api/tracker/projects/{project.id}/settings",
            json={"contract_rate": -50},
        )
        assert resp.status_code == 400
