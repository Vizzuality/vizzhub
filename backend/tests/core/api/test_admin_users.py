"""Tests for admin user management endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB, UserPublic, UserRole


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> UserDB:
    """Create an admin user in the test DB."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000001",
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN.value,
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def active_user(db_session: AsyncSession) -> UserDB:
    """Create an active regular user."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000010",
        email="active@test.com",
        first_name="Active",
        last_name="User",
        role=UserRole.USER.value,
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def inactive_user(db_session: AsyncSession) -> UserDB:
    """Create an inactive user."""
    user = UserDB(
        id="00000000-0000-0000-0000-000000000011",
        email="inactive@test.com",
        first_name="Inactive",
        last_name="User",
        role=UserRole.USER.value,
        active=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestUserPublicSchema:
    """UserPublic should include active field."""

    def test_user_public_includes_active_field(self):
        user = UserDB(
            id="00000000-0000-0000-0000-000000000001",
            email="test@test.com",
            first_name="Test",
            last_name="User",
            role=UserRole.USER.value,
            active=True,
        )
        public = UserPublic.model_validate(user)
        assert public.active is True

    def test_user_public_inactive_user(self):
        user = UserDB(
            id="00000000-0000-0000-0000-000000000002",
            email="inactive@test.com",
            first_name="Inactive",
            last_name="User",
            role=UserRole.USER.value,
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
