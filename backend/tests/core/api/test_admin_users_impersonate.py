"""Tests for admin user impersonation endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB, UserRole


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> UserDB:
    """Create an admin user in the test DB."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000001",
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN.value,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> UserDB:
    """Create a regular user in the test DB."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000002",
        email="user@test.com",
        first_name="Regular",
        last_name="User",
        role=UserRole.USER.value,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestImpersonate:
    """Tests for POST /admin/users/{user_id}/impersonate."""

    @pytest.mark.asyncio
    async def test_impersonate_returns_target_user(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        response = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@test.com"
        assert data["role"] == "user"
        assert data["id"] == str(regular_user.id)

    @pytest.mark.asyncio
    async def test_impersonate_sets_cookies(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        response = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        assert response.status_code == 200
        cookies = {c.name: c for c in response.cookies.jar}
        assert "access_token" in cookies
        assert "admin_token" in cookies

    @pytest.mark.asyncio
    async def test_impersonate_self_returns_400(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.post(
            f"/api/admin/users/{admin_user.id}/impersonate"
        )
        assert response.status_code == 400
        assert "Cannot impersonate yourself" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_impersonate_nonexistent_user_returns_404(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.post(
            "/api/admin/users/00000000-0000-0000-0000-000000000099/impersonate"
        )
        assert response.status_code == 404
