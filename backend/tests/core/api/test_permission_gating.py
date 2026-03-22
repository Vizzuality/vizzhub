"""Tests for permission-based endpoint gating."""

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.project import ProjectDB
from app.core.models.role import RoleDB
from app.core.models.user import UserDB
from app.core.permissions.roles import ROLE_PERMISSIONS
from app.main import app
from tests.conftest import seed_roles, assign_roles


def _user_permissions() -> list[str]:
    """Resolved permission list for a 'user' role."""
    return sorted(ROLE_PERMISSIONS["user"])


def _manager_permissions() -> list[str]:
    """Resolved permission list for 'user' + 'manager' roles."""
    perms = ROLE_PERMISSIONS["user"] | ROLE_PERMISSIONS["manager"]
    return sorted(perms)


@pytest_asyncio.fixture
async def roles(db_session: AsyncSession) -> dict[str, RoleDB]:
    return await seed_roles(db_session)


@pytest_asyncio.fixture
async def project_in_db(db_session: AsyncSession):
    """Minimal project for endpoint tests."""
    project = ProjectDB(
        id=UUID("00000000-0000-0000-0000-000000000099"),
        name="Test Project",
        status="active",
    )
    db_session.add(project)
    await db_session.commit()
    return project


class TestRegularUserDenied:
    """Regular users should be denied access to admin/manager endpoints."""

    @pytest_asyncio.fixture(autouse=True)
    async def _override_user(self):
        async def mock_user():
            return TokenData(
                user_id="00000000-0000-0000-0000-000000000010",
                email="user@test.com",
                roles=["user"],
                permissions=_user_permissions(),
            )
        app.dependency_overrides[get_current_user] = mock_user
        yield
        app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_user_cannot_create_project(self, client: AsyncClient):
        resp = await client.post(
            "/api/projects",
            json={"name": "New", "code": "NEW", "status": "active"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_user_cannot_list_admin_users(self, client: AsyncClient):
        resp = await client.get("/api/admin/users")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_user_cannot_list_roles(self, client: AsyncClient):
        resp = await client.get("/api/admin/users/roles")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_user_can_view_projects(self, client: AsyncClient):
        resp = await client.get("/api/projects")
        assert resp.status_code == 200


class TestManagerAccess:
    """Managers should access project management but not admin endpoints."""

    @pytest_asyncio.fixture(autouse=True)
    async def _override_manager(self):
        async def mock_manager():
            return TokenData(
                user_id="00000000-0000-0000-0000-000000000020",
                email="manager@test.com",
                roles=["user", "manager"],
                permissions=_manager_permissions(),
            )
        app.dependency_overrides[get_current_user] = mock_manager
        yield
        app.dependency_overrides.pop(get_current_user, None)

    @pytest.mark.asyncio
    async def test_manager_can_create_project(self, client: AsyncClient):
        resp = await client.post(
            "/api/projects",
            json={"name": "Manager Project", "code": "MGR"},
        )
        assert resp.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_manager_cannot_list_admin_users(self, client: AsyncClient):
        resp = await client.get("/api/admin/users")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_manager_cannot_list_roles(self, client: AsyncClient):
        resp = await client.get("/api/admin/users/roles")
        assert resp.status_code == 403
