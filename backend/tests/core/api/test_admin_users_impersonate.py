"""Tests for admin user impersonation endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import create_access_token
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


class TestStopImpersonate:
    """Tests for POST /admin/users/stop-impersonate."""

    @pytest.mark.asyncio
    async def test_stop_impersonate_restores_admin(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        # Set real admin JWT so impersonate stores a proper admin_token
        admin_jwt = create_access_token(
            data={
                "sub": str(admin_user.id),
                "email": admin_user.email,
                "role": admin_user.role,
            }
        )
        client.cookies.set("access_token", admin_jwt)

        # Impersonate
        resp = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        assert resp.status_code == 200

        # Extract cookies from impersonate response and set them on client
        for cookie in resp.cookies.jar:
            client.cookies.set(cookie.name, cookie.value)

        # Stop impersonating
        response = await client.post("/api/admin/users/stop-impersonate")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
        assert data["first_name"] == "Admin"
        assert data["last_name"] == "User"

    @pytest.mark.asyncio
    async def test_stop_impersonate_without_admin_token_returns_400(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.post("/api/admin/users/stop-impersonate")
        assert response.status_code == 400
        assert "Not currently impersonating" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_stop_impersonate_deletes_admin_token_cookie(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        # Set real admin JWT so impersonate stores a proper admin_token
        admin_jwt = create_access_token(
            data={
                "sub": str(admin_user.id),
                "email": admin_user.email,
                "role": admin_user.role,
            }
        )
        client.cookies.set("access_token", admin_jwt)

        # First impersonate
        resp = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        for cookie in resp.cookies.jar:
            client.cookies.set(cookie.name, cookie.value)

        # Stop
        response = await client.post("/api/admin/users/stop-impersonate")
        assert response.status_code == 200
        # admin_token should be deleted (max-age=0)
        cookies = {c.name: c for c in response.cookies.jar}
        assert "access_token" in cookies


class TestAuthMeImpersonation:
    """Tests for /auth/me is_impersonating field."""

    @pytest.mark.asyncio
    async def test_auth_me_not_impersonating(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["is_impersonating"] is False

    @pytest.mark.asyncio
    async def test_auth_me_while_impersonating(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        # Impersonate
        resp = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        for cookie in resp.cookies.jar:
            client.cookies.set(cookie.name, cookie.value)

        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["is_impersonating"] is True
        assert data["email"] == "user@test.com"


class TestLogoutClearsAdminToken:
    """Tests that logout deletes admin_token cookie."""

    @pytest.mark.asyncio
    async def test_logout_while_impersonating_clears_both_cookies(
        self, client: AsyncClient, admin_user: UserDB, regular_user: UserDB
    ):
        # Impersonate
        resp = await client.post(
            f"/api/admin/users/{regular_user.id}/impersonate"
        )
        for cookie in resp.cookies.jar:
            client.cookies.set(cookie.name, cookie.value)

        # Logout
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
