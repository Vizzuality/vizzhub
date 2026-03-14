"""Integration tests for authentication middleware behavior."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.auth import create_access_token
from app.core.models.project import ProjectDB


class TestAuthMiddlewareIntegration:
    """Test authentication middleware behavior."""

    @pytest.mark.asyncio
    async def test_dev_mode_bypasses_auth(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify development mode allows requests without JWT."""
        response = await client.get(f"/api/projects/{test_project.id}")

        assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_valid_jwt_is_accepted(
        self,
        client: AsyncClient,
        test_project: ProjectDB,
    ) -> None:
        """Verify valid JWT token is accepted."""
        token = create_access_token({"sub": "test-user", "roles": ["user"]})

        response = await client.get(
            f"/api/projects/{test_project.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_invalid_jwt_is_rejected(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify invalid JWT token is rejected."""
        response = await client.get(
            "/api/projects",
            headers={"Authorization": "Bearer invalid-token-here"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_jwt_is_rejected(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify expired JWT token is rejected."""
        token = create_access_token(
            {"sub": "test-user", "roles": ["user"]},
            expires_delta=timedelta(hours=-1),
        )

        response = await client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401
