"""Tests for OAuth service for Jira token management.

This module tests the OAuthService which handles OAuth 2.0 flows for
external services, specifically Jira authentication, token management,
and automatic token refresh.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
import respx
from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import decrypt_token, encrypt_token
from app.core.models.oauth import OAuthTokenDB
from app.core.services.oauth_service import OAuthService

TOKEN_URL = "https://auth.atlassian.com/oauth/token"
RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"


class TestAuthorizationURL:
    """Test OAuth authorization URL generation."""

    def test_oauth_service_get_jira_authorization_url_includes_state(self) -> None:
        """State parameter should be included when provided."""
        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client-id"
            mock_settings.jira_oauth_scopes = "read:jira-work"
            mock_settings.jira_oauth_redirect_uri = "http://localhost:8000/callback"

            url = OAuthService.get_jira_authorization_url(state="csrf-token-12345")

            assert "state=csrf-token-12345" in url


class TestCodeExchange:
    """Test OAuth authorization code exchange."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_oauth_service_exchange_code_stores_token_in_database(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should persist token to oauth_tokens table."""
        respx.post(TOKEN_URL).mock(
            return_value=Response(200, json={
                "access_token": "stored-token",
                "refresh_token": "stored-refresh",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read:jira-work",
            })
        )
        respx.get(RESOURCES_URL).mock(
            return_value=Response(200, json=[
                {"id": "cloud-123", "url": "https://test.atlassian.net"}
            ])
        )

        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client"
            mock_settings.jira_oauth_client_secret = "test-secret"
            mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

            await OAuthService.exchange_jira_code_for_token("code", db_session)

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        db_token = result.scalar_one_or_none()

        assert db_token is not None
        assert decrypt_token(db_token.access_token) == "stored-token"
        assert decrypt_token(db_token.refresh_token) == "stored-refresh"
        assert db_token.provider == "jira"

    @pytest.mark.asyncio
    @respx.mock
    async def test_oauth_service_exchange_code_replaces_existing_token(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should delete old Jira token before creating new one."""
        existing_token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("old-token"),
            refresh_token=encrypt_token("old-refresh"),
            cloud_id="old-cloud-id",
        )
        db_session.add(existing_token)
        await db_session.commit()

        respx.post(TOKEN_URL).mock(
            return_value=Response(200, json={
                "access_token": "new-token",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            })
        )
        respx.get(RESOURCES_URL).mock(
            return_value=Response(200, json=[
                {"id": "new-cloud-id", "url": "https://new.atlassian.net"}
            ])
        )

        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client"
            mock_settings.jira_oauth_client_secret = "test-secret"
            mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

            await OAuthService.exchange_jira_code_for_token("code", db_session)

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        tokens = result.scalars().all()

        assert len(tokens) == 1
        assert decrypt_token(tokens[0].access_token) == "new-token"
        assert tokens[0].cloud_id == "new-cloud-id"

    @pytest.mark.asyncio
    @respx.mock
    async def test_oauth_service_exchange_code_calculates_expiration(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should set expires_at correctly from expires_in."""
        respx.post(TOKEN_URL).mock(
            return_value=Response(200, json={
                "access_token": "test-token",
                "expires_in": 3600,
            })
        )
        respx.get(RESOURCES_URL).mock(
            return_value=Response(200, json=[
                {"id": "cloud-id", "url": "https://test.atlassian.net"}
            ])
        )

        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client"
            mock_settings.jira_oauth_client_secret = "test-secret"
            mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

            before = datetime.now(timezone.utc)
            token = await OAuthService.exchange_jira_code_for_token(
                "code", db_session
            )
            after = datetime.now(timezone.utc)

        assert token.expires_at is not None
        expected_min = before + timedelta(seconds=3600)
        expected_max = after + timedelta(seconds=3600)
        assert expected_min <= token.expires_at <= expected_max

    @pytest.mark.asyncio
    @respx.mock
    async def test_oauth_service_exchange_code_handles_api_failure(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should raise exception on API error."""
        respx.post(TOKEN_URL).mock(return_value=Response(400))

        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client"
            mock_settings.jira_oauth_client_secret = "test-secret"
            mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

            with pytest.raises(Exception):
                await OAuthService.exchange_jira_code_for_token(
                    "invalid-code", db_session
                )

    @pytest.mark.asyncio
    @respx.mock
    async def test_oauth_service_exchange_code_missing_refresh_token_handled(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should handle missing refresh_token in response."""
        respx.post(TOKEN_URL).mock(
            return_value=Response(200, json={
                "access_token": "access-only-token",
                "expires_in": 3600,
            })
        )
        respx.get(RESOURCES_URL).mock(
            return_value=Response(200, json=[
                {"id": "cloud-id", "url": "https://test.atlassian.net"}
            ])
        )

        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client"
            mock_settings.jira_oauth_client_secret = "test-secret"
            mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

            token = await OAuthService.exchange_jira_code_for_token(
                "code", db_session
            )

        assert decrypt_token(token.access_token) == "access-only-token"
        assert token.refresh_token is None


class TestTokenRefresh:
    """Test OAuth token refresh functionality."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_oauth_service_refresh_token_calls_atlassian_endpoint(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_token should POST with refresh_token grant."""
        existing_token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("old-access-token"),
            refresh_token=encrypt_token("valid-refresh-token"),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db_session.add(existing_token)
        await db_session.commit()

        token_route = respx.post(TOKEN_URL).mock(
            return_value=Response(200, json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            })
        )

        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client"
            mock_settings.jira_oauth_client_secret = "test-secret"

            await OAuthService.refresh_jira_token(db_session)

        assert token_route.called
        request = token_route.calls.last.request
        body = request.content.decode()
        assert "grant_type=refresh_token" in body
        assert "refresh_token=valid-refresh-token" in body

    @pytest.mark.asyncio
    @respx.mock
    async def test_oauth_service_refresh_token_updates_existing_record(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_token should update existing token not create new one."""
        existing_token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("old-token"),
            refresh_token=encrypt_token("refresh-token"),
            cloud_id="cloud-id-123",
        )
        db_session.add(existing_token)
        await db_session.commit()
        token_id = existing_token.id

        respx.post(TOKEN_URL).mock(
            return_value=Response(200, json={
                "access_token": "refreshed-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            })
        )

        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client"
            mock_settings.jira_oauth_client_secret = "test-secret"

            refreshed = await OAuthService.refresh_jira_token(db_session)

        assert refreshed.id == token_id
        assert decrypt_token(refreshed.access_token) == "refreshed-token"

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        tokens = result.scalars().all()
        assert len(tokens) == 1

    @pytest.mark.asyncio
    async def test_oauth_service_refresh_token_no_token_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_token should return None when no token exists."""
        result = await OAuthService.refresh_jira_token(db_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_oauth_service_refresh_token_no_refresh_token_returns_none(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_token should return None when refresh_token is null."""
        token_without_refresh = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("access-token-only"),
            refresh_token=None,
        )
        db_session.add(token_without_refresh)
        await db_session.commit()

        result = await OAuthService.refresh_jira_token(db_session)

        assert result is None


class TestGetValidToken:
    """Test get_valid_jira_token functionality."""

    @pytest.mark.asyncio
    async def test_oauth_service_get_valid_token_returns_fresh_token(
        self, db_session: AsyncSession
    ) -> None:
        """get_valid_token should return token when not expired."""
        fresh_token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("fresh-token"),
            refresh_token=encrypt_token("refresh-token"),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db_session.add(fresh_token)
        await db_session.commit()

        token = await OAuthService.get_valid_jira_token(db_session)

        assert token == "fresh-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_oauth_service_get_valid_token_refreshes_when_expired(
        self, db_session: AsyncSession
    ) -> None:
        """get_valid_token should auto-refresh if expired."""
        expired_token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("expired-token"),
            refresh_token=encrypt_token("valid-refresh"),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db_session.add(expired_token)
        await db_session.commit()

        respx.post(TOKEN_URL).mock(
            return_value=Response(200, json={
                "access_token": "refreshed-token",
                "expires_in": 3600,
            })
        )

        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client"
            mock_settings.jira_oauth_client_secret = "test-secret"

            token = await OAuthService.get_valid_jira_token(db_session)

        assert token == "refreshed-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_oauth_service_get_valid_token_refreshes_within_5min_buffer(
        self, db_session: AsyncSession
    ) -> None:
        """get_valid_token should refresh 5 minutes before expiry."""
        soon_to_expire = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("about-to-expire"),
            refresh_token=encrypt_token("refresh-token"),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
        )
        db_session.add(soon_to_expire)
        await db_session.commit()

        respx.post(TOKEN_URL).mock(
            return_value=Response(200, json={
                "access_token": "pre-emptively-refreshed",
                "expires_in": 3600,
            })
        )

        with patch("app.core.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client"
            mock_settings.jira_oauth_client_secret = "test-secret"

            token = await OAuthService.get_valid_jira_token(db_session)

        assert token == "pre-emptively-refreshed"

    @pytest.mark.asyncio
    async def test_oauth_service_get_valid_token_returns_none_when_missing(
        self, db_session: AsyncSession
    ) -> None:
        """get_valid_token should return None when no token exists."""
        token = await OAuthService.get_valid_jira_token(db_session)

        assert token is None
