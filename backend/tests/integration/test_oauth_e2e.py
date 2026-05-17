"""OAuth end-to-end integration tests."""

import pytest
from httpx import AsyncClient


class TestOAuthE2EIntegration:
    """Test OAuth flow end-to-end with mocked external services."""

    @pytest.mark.asyncio
    async def test_oauth_authorize_returns_redirect_url(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify OAuth authorize endpoint returns a valid redirect URL."""
        response = await client.get("/api/oauth/jira/authorize")

        # Should redirect or return auth URL
        assert response.status_code in [200, 302, 307]

        if response.status_code == 200:
            data = response.json()
            assert "auth_url" in data or "authorization_url" in data

    @pytest.mark.asyncio
    async def test_oauth_callback_validates_state(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify OAuth callback rejects invalid state parameter."""
        response = await client.get(
            "/api/oauth/jira/callback",
            params={"code": "fake-code", "state": "invalid-state"},
        )

        # Should reject invalid state
        assert response.status_code in [400, 401, 403]

    @pytest.mark.asyncio
    async def test_oauth_status_returns_not_connected_initially(
        self,
        client: AsyncClient,
    ) -> None:
        """Verify OAuth status shows not connected when no token exists."""
        response = await client.get("/api/oauth/jira/status")

        assert response.status_code == 200
        data = response.json()
        assert data.get("authenticated") is False
