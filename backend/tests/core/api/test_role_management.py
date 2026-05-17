"""Tests for role listing and assignment endpoints."""

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.role import RoleDB
from app.core.models.user import UserDB
from tests.conftest import assign_roles, seed_roles


@pytest_asyncio.fixture
async def roles(db_session: AsyncSession) -> dict[str, RoleDB]:
    return await seed_roles(db_session)


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, roles) -> UserDB:
    user = UserDB(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email="admin@test.com",
        active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await assign_roles(db_session, user.id, [roles["user"].id, roles["admin"].id])
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def basic_user(db_session: AsyncSession, roles) -> UserDB:
    user = UserDB(
        id=UUID("00000000-0000-0000-0000-000000000010"),
        email="basic@test.com",
        active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await assign_roles(db_session, user.id, [roles["user"].id])
    await db_session.commit()
    return user


class TestListRoles:
    @pytest.mark.asyncio
    async def test_returns_all_seeded_roles(self, client: AsyncClient, admin_user, roles):
        resp = await client.get("/api/admin/users/roles")
        assert resp.status_code == 200
        data = resp.json()
        names = {r["name"] for r in data}
        assert names == {"user", "manager", "admin"}

    @pytest.mark.asyncio
    async def test_roles_have_expected_fields(self, client: AsyncClient, admin_user, roles):
        resp = await client.get("/api/admin/users/roles")
        data = resp.json()
        for role in data:
            assert "id" in role
            assert "name" in role
            assert "description" in role


class TestAssignRoles:
    @pytest.mark.asyncio
    async def test_assign_manager_role(self, client: AsyncClient, admin_user, basic_user, roles):
        resp = await client.put(
            f"/api/admin/users/{basic_user.id}/roles",
            json={"roles": ["user", "manager"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["roles"]) == {"user", "manager"}

    @pytest.mark.asyncio
    async def test_requires_user_role(self, client: AsyncClient, admin_user, basic_user, roles):
        resp = await client.put(
            f"/api/admin/users/{basic_user.id}/roles",
            json={"roles": ["manager"]},
        )
        assert resp.status_code == 400
        assert "user" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_rejects_unknown_role(self, client: AsyncClient, admin_user, basic_user, roles):
        resp = await client.put(
            f"/api/admin/users/{basic_user.id}/roles",
            json={"roles": ["user", "nonexistent"]},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_user(self, client: AsyncClient, admin_user, roles):
        resp = await client.put(
            "/api/admin/users/00000000-0000-0000-0000-999999999999/roles",
            json={"roles": ["user"]},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_replaces_all_roles(self, client: AsyncClient, admin_user, basic_user, roles):
        """Assigning roles replaces existing ones, doesn't append."""
        await client.put(
            f"/api/admin/users/{basic_user.id}/roles",
            json={"roles": ["user", "manager"]},
        )
        resp = await client.put(
            f"/api/admin/users/{basic_user.id}/roles",
            json={"roles": ["user"]},
        )
        assert resp.status_code == 200
        assert resp.json()["roles"] == ["user"]
