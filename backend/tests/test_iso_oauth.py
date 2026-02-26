"""Tests for ISO Google Workspace OAuth."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.core.token_encryption import decrypt_token, encrypt_token
from app.models.oauth import OAuthTokenDB


class TestGoogleWorkspaceConfig:
    def test_config_has_google_workspace_fields(self) -> None:
        get_settings.cache_clear()
        settings = get_settings()
        assert hasattr(settings, "google_workspace_client_id")
        assert hasattr(settings, "google_workspace_client_secret")
        assert settings.google_workspace_client_id == ""
        assert settings.google_workspace_client_secret == ""


class TestGoogleWorkspaceOAuthService:
    def test_authorization_url_contains_required_params(self) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        url = GoogleWorkspaceOAuth.get_authorization_url(
            state="test-state",
            redirect_uri="http://localhost:8000/api/iso/config/google-workspace/callback",
        )
        assert "accounts.google.com" in url
        assert "test-state" in url
        assert "response_type=code" in url
        assert "access_type=offline" in url
        assert "admin.directory.user.readonly" in url
        assert "redirect_uri=" in url

    def test_authorization_url_includes_domain(self) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        url = GoogleWorkspaceOAuth.get_authorization_url(
            state="s",
            redirect_uri="http://localhost:8000/callback",
            domain="empresa.com",
        )
        assert "empresa.com" in url

    @pytest.mark.asyncio
    async def test_exchange_code_stores_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "ya29.test-access-token",
            "refresh_token": "1//test-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/admin.directory.user.readonly",
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            token = await GoogleWorkspaceOAuth.exchange_code_for_token(
                code="test-code",
                domain="empresa.com",
                redirect_uri="http://localhost:8000/callback",
                db=db_session,
            )

        assert token.provider == "google_workspace"
        assert decrypt_token(token.access_token) == "ya29.test-access-token"
        assert decrypt_token(token.refresh_token) == "1//test-refresh-token"
        assert token.site_url == "empresa.com"
        assert token.expires_at is not None

    @pytest.mark.asyncio
    async def test_exchange_code_replaces_existing_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("old-token"),
            site_url="old.com",
        )
        db_session.add(existing)
        await db_session.flush()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            token = await GoogleWorkspaceOAuth.exchange_code_for_token(
                code="code",
                domain="new.com",
                redirect_uri="http://localhost:8000/callback",
                db=db_session,
            )

        assert decrypt_token(token.access_token) == "new-token"
        assert token.site_url == "new.com"

    @pytest.mark.asyncio
    async def test_refresh_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("expired"),
            refresh_token=encrypt_token("valid-refresh"),
            site_url="test.com",
        )
        db_session.add(existing)
        await db_session.flush()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "refreshed-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_response.raise_for_status = MagicMock()

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            refreshed = await GoogleWorkspaceOAuth.refresh_token(db_session)

        assert refreshed is not None
        assert decrypt_token(refreshed.access_token) == "refreshed-token"

    @pytest.mark.asyncio
    async def test_refresh_returns_none_when_no_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        result = await GoogleWorkspaceOAuth.refresh_token(db_session)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_valid_token(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("valid-token"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            site_url="test.com",
        )
        db_session.add(existing)
        await db_session.flush()

        token = await GoogleWorkspaceOAuth.get_valid_token(db_session)
        assert token == "valid-token"

    @pytest.mark.asyncio
    async def test_get_valid_token_returns_none(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        token = await GoogleWorkspaceOAuth.get_valid_token(db_session)
        assert token is None

    @pytest.mark.asyncio
    async def test_disconnect(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("token"),
            site_url="test.com",
        )
        db_session.add(existing)
        await db_session.flush()

        await GoogleWorkspaceOAuth.disconnect(db_session)
        token = await GoogleWorkspaceOAuth.get_valid_token(db_session)
        assert token is None

    @pytest.mark.asyncio
    async def test_get_status_connected(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        existing = OAuthTokenDB(
            provider="google_workspace",
            access_token=encrypt_token("token"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            site_url="empresa.com",
        )
        db_session.add(existing)
        await db_session.flush()

        status = await GoogleWorkspaceOAuth.get_status(db_session)
        assert status["connected"] is True
        assert status["domain"] == "empresa.com"

    @pytest.mark.asyncio
    async def test_get_status_disconnected(self, db_session) -> None:
        from app.modules.iso.services.google_workspace_oauth import (
            GoogleWorkspaceOAuth,
        )

        status = await GoogleWorkspaceOAuth.get_status(db_session)
        assert status["connected"] is False
        assert status["domain"] is None


class TestIsoConfigEndpoints:
    @pytest.mark.asyncio
    async def test_status_disconnected(self, client: AsyncClient) -> None:
        response = await client.get("/api/iso/config/google-workspace")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["domain"] is None

    @pytest.mark.asyncio
    async def test_authorize_redirects(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/iso/config/google-workspace/authorize",
            params={"domain": "test.com"},
            follow_redirects=False,
        )
        assert response.status_code == 307
        location = response.headers["location"]
        assert "accounts.google.com" in location
        assert "test.com" in location

    @pytest.mark.asyncio
    async def test_authorize_requires_domain(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/iso/config/google-workspace/authorize",
            follow_redirects=False,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_callback_rejects_missing_state(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/iso/config/google-workspace/callback",
            params={"code": "test-code"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, client: AsyncClient) -> None:
        response = await client.delete("/api/iso/config/google-workspace/disconnect")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_status_after_manual_token_insert(
        self, client: AsyncClient, db_session
    ) -> None:
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="test-token",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        response = await client.get("/api/iso/config/google-workspace")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["domain"] == "empresa.com"

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(
        self, client: AsyncClient, db_session
    ) -> None:
        token = OAuthTokenDB(
            provider="google_workspace",
            access_token="test-token",
            site_url="empresa.com",
        )
        db_session.add(token)
        await db_session.flush()

        response = await client.delete("/api/iso/config/google-workspace/disconnect")
        assert response.status_code == 200

        status_response = await client.get("/api/iso/config/google-workspace")
        assert status_response.json()["connected"] is False
