"""Tests for admin user management endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB, UserPublic, UserRole


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
