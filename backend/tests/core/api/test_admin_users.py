"""Tests for admin user management endpoints."""

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.core.models.role import RoleDB
from app.core.models.user import UserDB, UserPublic
from tests.conftest import seed_roles, assign_roles


@pytest_asyncio.fixture
async def roles(db_session: AsyncSession) -> dict[str, RoleDB]:
    """Seed roles once for all user fixtures in this module."""
    return await seed_roles(db_session)


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, roles) -> UserDB:
    """Create an admin user in the test DB."""
    user = UserDB(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await assign_roles(db_session, user.id, [roles["user"].id, roles["admin"].id])
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession, roles) -> UserDB:
    """Create an active regular user."""
    user = UserDB(
        id=UUID("00000000-0000-0000-0000-000000000010"),
        email="active@test.com",
        first_name="Active",
        last_name="User",
        active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await assign_roles(db_session, user.id, [roles["user"].id])
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession, roles) -> UserDB:
    """Create an inactive user."""
    user = UserDB(
        id=UUID("00000000-0000-0000-0000-000000000011"),
        email="inactive@test.com",
        first_name="Inactive",
        last_name="User",
        active=False,
    )
    db_session.add(user)
    await db_session.flush()
    await assign_roles(db_session, user.id, [roles["user"].id])
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestUserPublicSchema:
    """UserPublic should include active field."""

    def test_user_public_includes_active_field(self):
        user = UserDB(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            email="test@test.com",
            first_name="Test",
            last_name="User",
            active=True,
        )
        public = UserPublic.model_validate(user)
        assert public.active is True

    def test_user_public_inactive_user(self):
        user = UserDB(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            email="inactive@test.com",
            first_name="Inactive",
            last_name="User",
            active=False,
        )
        public = UserPublic.model_validate(user)
        assert public.active is False


class TestListUsers:
    """Tests for GET /admin/users."""

    @pytest.mark.asyncio
    async def test_list_users_excludes_inactive_by_default(
        self, client: AsyncClient, admin_user: UserDB, active_user: UserDB, inactive_user: UserDB
    ):
        response = await client.get("/api/admin/users")
        assert response.status_code == 200
        emails = [u["email"] for u in response.json()]
        assert "active@test.com" in emails
        assert "admin@test.com" in emails
        assert "inactive@test.com" not in emails

    @pytest.mark.asyncio
    async def test_list_users_includes_inactive_when_requested(
        self, client: AsyncClient, admin_user: UserDB, active_user: UserDB, inactive_user: UserDB
    ):
        response = await client.get("/api/admin/users?include_inactive=true")
        assert response.status_code == 200
        emails = [u["email"] for u in response.json()]
        assert "inactive@test.com" in emails
        assert "active@test.com" in emails

    @pytest.mark.asyncio
    async def test_list_users_response_includes_active_field(
        self, client: AsyncClient, admin_user: UserDB, active_user: UserDB, inactive_user: UserDB
    ):
        response = await client.get("/api/admin/users?include_inactive=true")
        assert response.status_code == 200
        users_by_email = {u["email"]: u for u in response.json()}
        assert users_by_email["active@test.com"]["active"] is True
        assert users_by_email["inactive@test.com"]["active"] is False


class TestUpdateUser:
    """Tests for PATCH /admin/users/{user_id}."""

    @pytest.mark.asyncio
    async def test_deactivate_user(
        self, client: AsyncClient, admin_user: UserDB, active_user: UserDB
    ):
        response = await client.patch(
            f"/api/admin/users/{active_user.id}",
            json={"active": False},
        )
        assert response.status_code == 200
        assert response.json()["active"] is False

    @pytest.mark.asyncio
    async def test_reactivate_user(
        self, client: AsyncClient, admin_user: UserDB, inactive_user: UserDB
    ):
        response = await client.patch(
            f"/api/admin/users/{inactive_user.id}",
            json={"active": True},
        )
        assert response.status_code == 200
        assert response.json()["active"] is True

    @pytest.mark.asyncio
    async def test_cannot_deactivate_self(
        self, client: AsyncClient, admin_user: UserDB
    ):
        response = await client.patch(
            f"/api/admin/users/{admin_user.id}",
            json={"active": False},
        )
        assert response.status_code == 400
        assert "Cannot deactivate yourself" in response.json()["detail"]


class TestInactiveUserLogin:
    """Tests for login block on inactive users."""

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_login(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """An existing inactive user should get 403 on Google login."""
        roles = await seed_roles(db_session)
        user = UserDB(
            id=UUID("00000000-0000-0000-0000-000000000020"),
            email="deactivated@test.com",
            first_name="Deactivated",
            last_name="User",
            active=False,
        )
        db_session.add(user)
        await db_session.flush()
        await assign_roles(db_session, user.id, [roles["user"].id])
        await db_session.commit()

        mock_idinfo = {
            "email": "deactivated@test.com",
            "given_name": "Deactivated",
            "family_name": "User",
            "picture": None,
        }
        with patch("app.core.api.auth.id_token.verify_oauth2_token", return_value=mock_idinfo), \
             patch("app.core.api.auth.settings") as mock_settings:
            mock_settings.allowed_google_domain = None
            mock_settings.initial_admin_email = None
            response = await client.post(
                "/api/auth/google",
                json={"credential": "fake-google-token"},
            )
        assert response.status_code == 403
        assert "Account deactivated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_active_user_can_login(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """An existing active user should be able to login."""
        roles = await seed_roles(db_session)
        user = UserDB(
            id=UUID("00000000-0000-0000-0000-000000000021"),
            email="active-login@test.com",
            first_name="Active",
            last_name="Login",
            active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await assign_roles(db_session, user.id, [roles["user"].id])
        await db_session.commit()

        mock_idinfo = {
            "email": "active-login@test.com",
            "given_name": "Active",
            "family_name": "Login",
            "picture": None,
        }
        with patch("app.core.api.auth.id_token.verify_oauth2_token", return_value=mock_idinfo), \
             patch("app.core.api.auth.settings") as mock_settings:
            mock_settings.allowed_google_domain = None
            mock_settings.initial_admin_email = None
            response = await client.post(
                "/api/auth/google",
                json={"credential": "fake-google-token"},
            )
        assert response.status_code == 200
