"""Tests for Integration Admin API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.oauth import OAuthTokenDB
from app.core.services.copper_client import CopperAuthError
from app.core.token_encryption import decrypt_token, encrypt_token


class TestIntegrationsStatus:
    """Tests for GET /admin/integrations/status."""

    @pytest.mark.asyncio
    async def test_all_disconnected(self, client: AsyncClient) -> None:
        """Status returns all providers as disconnected when no tokens exist."""
        response = await client.get("/api/admin/integrations/status")
        assert response.status_code == 200
        data = response.json()

        for provider in ("jira", "google_workspace", "github", "slack"):
            assert data[provider]["connected"] is False
            assert data[provider]["expires_at"] is None
            assert data[provider]["token_type"] is None
            assert data[provider]["site_url"] is None
            assert data[provider]["created_at"] is None

        assert data["slack_settings"] == {"leadership_channel_id": None}


class TestGitHubIntegration:
    """Tests for GitHub token endpoints."""

    @pytest.mark.asyncio
    async def test_save_github_pat(self, client: AsyncClient) -> None:
        """PUT /github saves a PAT and returns connected status."""
        response = await client.put(
            "/api/admin/integrations/github",
            json={"token": "ghp_test1234567890"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["token_type"] == "pat"
        assert data["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_github_token(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """DELETE /github removes the token."""
        record = OAuthTokenDB(
            provider="github",
            access_token=encrypt_token("ghp_test"),
            token_type="pat",
        )
        db_session.add(record)
        await db_session.commit()

        response = await client.delete("/api/admin/integrations/github")
        assert response.status_code == 200
        assert response.json() == {"status": "disconnected"}

    @pytest.mark.asyncio
    async def test_delete_github_404(self, client: AsyncClient) -> None:
        """DELETE /github returns 404 when no token exists."""
        response = await client.delete("/api/admin/integrations/github")
        assert response.status_code == 404
        assert "GitHub token not found" in response.json()["detail"]


class TestSlackIntegration:
    """Tests for Slack token and settings endpoints."""

    @pytest.mark.asyncio
    async def test_save_slack_token(self, client: AsyncClient) -> None:
        """PUT /slack saves a bot token and returns connected status."""
        response = await client.put(
            "/api/admin/integrations/slack",
            json={"token": "xoxb-test-token-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["token_type"] == "bot"
        assert data["expires_at"] is None

    @pytest.mark.asyncio
    async def test_delete_slack_token(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """DELETE /slack removes the token."""
        record = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test"),
            token_type="bot",
        )
        db_session.add(record)
        await db_session.commit()

        response = await client.delete("/api/admin/integrations/slack")
        assert response.status_code == 200
        assert response.json() == {"status": "disconnected"}

    @pytest.mark.asyncio
    async def test_update_slack_settings(self, client: AsyncClient) -> None:
        """PUT /slack/settings updates the leadership channel ID."""
        response = await client.put(
            "/api/admin/integrations/slack/settings",
            json={"leadership_channel_id": "C12345678"},
        )
        assert response.status_code == 200
        assert response.json() == {"leadership_channel_id": "C12345678"}

    @pytest.mark.asyncio
    async def test_slack_channels(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """GET /slack/channels returns channel list when token exists."""
        record = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test"),
            token_type="bot",
        )
        db_session.add(record)
        await db_session.commit()

        mock_channels = [
            {"id": "C001", "name": "general", "is_private": False},
            {"id": "C002", "name": "secret", "is_private": True},
        ]
        with patch(
            "app.modules.notifications.public.SlackService.list_channels",
            new_callable=AsyncMock,
            return_value=mock_channels,
        ):
            response = await client.get("/api/admin/integrations/slack/channels")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "C001"
        assert data[0]["name"] == "general"
        assert data[0]["is_private"] is False
        assert data[1]["id"] == "C002"
        assert data[1]["is_private"] is True

    @pytest.mark.asyncio
    async def test_slack_test_connection(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """POST /slack/test returns connection result."""
        record = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test"),
            token_type="bot",
        )
        db_session.add(record)
        await db_session.commit()

        mock_response = {"ok": True, "team": "Test Team", "bot_id": "B12345"}
        with patch(
            "app.modules.notifications.public.SlackService.test_connection",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await client.post("/api/admin/integrations/slack/test")

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["team"] == "Test Team"
        assert data["bot_id"] == "B12345"

    @pytest.mark.asyncio
    async def test_slack_channels_no_token_400(self, client: AsyncClient) -> None:
        """GET /slack/channels returns 400 when no Slack token exists."""
        response = await client.get("/api/admin/integrations/slack/channels")
        assert response.status_code == 400
        assert "No Slack token configured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_slack_test_no_token(self, client: AsyncClient) -> None:
        """POST /slack/test returns ok=False when no token exists."""
        response = await client.post("/api/admin/integrations/slack/test")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "No Slack token configured" in data["error"]


class TestCopperIntegration:
    """Tests for the Copper API key endpoints."""

    @pytest.mark.asyncio
    async def test_save_copper_credentials_encrypts_key(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        with patch(
            "app.core.services.copper_client.CopperClient.get_account",
            new=AsyncMock(return_value={"id": 12973, "name": "Vizzuality"}),
        ):
            response = await client.put(
                "/api/admin/integrations/copper",
                json={"api_key": "copper-key-1", "user_email": "owner@example.com"},
            )

        assert response.status_code == 200
        assert response.json()["connected"] is True
        record = (
            await db_session.execute(select(OAuthTokenDB).where(OAuthTokenDB.provider == "copper"))
        ).scalar_one()
        assert record.access_token != "copper-key-1"
        assert decrypt_token(record.access_token) == "copper-key-1"

        status_resp = await client.get("/api/admin/integrations/status")
        data = status_resp.json()
        assert data["copper"]["connected"] is True
        assert data["copper_settings"] == {"user_email": "owner@example.com"}

    @pytest.mark.asyncio
    async def test_save_copper_rejects_credentials_copper_refuses(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        with patch(
            "app.core.services.copper_client.CopperClient.get_account",
            new=AsyncMock(side_effect=CopperAuthError("authentication error")),
        ):
            response = await client.put(
                "/api/admin/integrations/copper",
                json={"api_key": "bad", "user_email": "typo@example.com"},
            )

        assert response.status_code == 400
        stored = (
            await db_session.execute(select(OAuthTokenDB).where(OAuthTokenDB.provider == "copper"))
        ).scalar_one_or_none()
        assert stored is None

    @pytest.mark.asyncio
    async def test_delete_copper_credentials(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        db_session.add(
            OAuthTokenDB(provider="copper", access_token=encrypt_token("k"), token_type="api_key")
        )
        await db_session.commit()

        response = await client.delete("/api/admin/integrations/copper")

        assert response.status_code == 200
        data = (await client.get("/api/admin/integrations/status")).json()
        assert data["copper"]["connected"] is False
        assert data["copper_settings"] == {"user_email": None}
