"""Tests for OAuth service for Jira token management.

This module tests the OAuthService which handles OAuth 2.0 flows for
external services, specifically Jira authentication, token management,
and automatic token refresh.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth import OAuthTokenDB
from app.services.oauth_service import OAuthService


class TestAuthorizationURL:
    """Test OAuth authorization URL generation."""

    def test_oauth_service_get_jira_authorization_url_contains_required_params(
        self,
    ) -> None:
        """Authorization URL should contain all required OAuth parameters."""
        with patch("app.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client-id"
            mock_settings.jira_oauth_scopes = "read:jira-work read:jira-user"
            mock_settings.jira_oauth_redirect_uri = "http://localhost:8000/callback"

            url = OAuthService.get_jira_authorization_url()

            # Verify URL contains required parameters
            assert "https://auth.atlassian.com/authorize?" in url
            assert "client_id=test-client-id" in url
            assert "scope=read%3Ajira-work+read%3Ajira-user" in url
            assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback" in url
            assert "response_type=code" in url
            assert "audience=api.atlassian.com" in url
            assert "prompt=consent" in url

    def test_oauth_service_get_jira_authorization_url_includes_state(self) -> None:
        """State parameter should be included when provided."""
        with patch("app.services.oauth_service.settings") as mock_settings:
            mock_settings.jira_oauth_client_id = "test-client-id"
            mock_settings.jira_oauth_scopes = "read:jira-work"
            mock_settings.jira_oauth_redirect_uri = "http://localhost:8000/callback"

            url = OAuthService.get_jira_authorization_url(state="csrf-token-12345")

            assert "state=csrf-token-12345" in url


class TestCodeExchange:
    """Test OAuth authorization code exchange."""

    @pytest_asyncio.fixture
    async def mock_httpx_client(self) -> AsyncMock:
        """Mock httpx.AsyncClient for testing."""
        return AsyncMock(spec=httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_oauth_service_exchange_code_calls_atlassian_token_endpoint(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should POST to Atlassian token endpoint with correct params."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock token response (json() is sync, not async)
            token_response = MagicMock()
            token_response.json.return_value = {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read:jira-work",
            }
            token_response.raise_for_status = MagicMock()

            # Mock resources response (json() is sync, not async)
            resources_response = MagicMock()
            resources_response.json.return_value = [
                {"id": "cloud-id-123", "url": "https://test.atlassian.net"}
            ]
            resources_response.raise_for_status = MagicMock()

            mock_client.post.return_value = token_response
            mock_client.get.return_value = resources_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"
                mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

                await OAuthService.exchange_jira_code_for_token(
                    "auth-code-123", db_session
                )

            # Verify token endpoint was called with correct data
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == OAuthService.JIRA_TOKEN_URL
            assert call_args[1]["data"]["grant_type"] == "authorization_code"
            assert call_args[1]["data"]["client_id"] == "test-client"
            assert call_args[1]["data"]["client_secret"] == "test-secret"
            assert call_args[1]["data"]["code"] == "auth-code-123"

    @pytest.mark.asyncio
    async def test_oauth_service_exchange_code_fetches_accessible_resources(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should fetch Jira cloud ID after token exchange."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            token_response = MagicMock()
            token_response.json.return_value = {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
            }
            token_response.raise_for_status = MagicMock()

            resources_response = MagicMock()
            resources_response.json.return_value = [
                {"id": "cloud-id-456", "url": "https://mycompany.atlassian.net"}
            ]
            resources_response.raise_for_status = MagicMock()

            mock_client.post.return_value = token_response
            mock_client.get.return_value = resources_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"
                mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

                token = await OAuthService.exchange_jira_code_for_token(
                    "auth-code", db_session
                )

            # Verify accessible resources endpoint was called
            mock_client.get.assert_called_once_with(
                OAuthService.JIRA_ACCESSIBLE_RESOURCES_URL,
                headers={"Authorization": "Bearer mock-access-token"},
            )

            # Verify cloud_id was stored
            assert token.cloud_id == "cloud-id-456"
            assert token.site_url == "https://mycompany.atlassian.net"

    @pytest.mark.asyncio
    async def test_oauth_service_exchange_code_stores_token_in_database(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should persist token to oauth_tokens table."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            token_response = MagicMock()
            token_response.json.return_value = {
                "access_token": "stored-token",
                "refresh_token": "stored-refresh",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read:jira-work",
            }
            token_response.raise_for_status = MagicMock()

            resources_response = MagicMock()
            resources_response.json.return_value = [
                {"id": "cloud-123", "url": "https://test.atlassian.net"}
            ]
            resources_response.raise_for_status = MagicMock()

            mock_client.post.return_value = token_response
            mock_client.get.return_value = resources_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"
                mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

                token = await OAuthService.exchange_jira_code_for_token(
                    "code", db_session
                )

            # Verify token is in database
            result = await db_session.execute(
                select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
            )
            db_token = result.scalar_one_or_none()

            assert db_token is not None
            assert db_token.access_token == "stored-token"
            assert db_token.refresh_token == "stored-refresh"
            assert db_token.provider == "jira"

    @pytest.mark.asyncio
    async def test_oauth_service_exchange_code_replaces_existing_token(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should delete old Jira token before creating new one."""
        # Create existing token
        existing_token = OAuthTokenDB(
            provider="jira",
            access_token="old-token",
            refresh_token="old-refresh",
            cloud_id="old-cloud-id",
        )
        db_session.add(existing_token)
        await db_session.commit()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            token_response = MagicMock()
            token_response.json.return_value = {
                "access_token": "new-token",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            }
            token_response.raise_for_status = MagicMock()

            resources_response = MagicMock()
            resources_response.json.return_value = [
                {"id": "new-cloud-id", "url": "https://new.atlassian.net"}
            ]
            resources_response.raise_for_status = MagicMock()

            mock_client.post.return_value = token_response
            mock_client.get.return_value = resources_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"
                mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

                new_token = await OAuthService.exchange_jira_code_for_token(
                    "code", db_session
                )

        # Verify only one token exists with new values
        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        tokens = result.scalars().all()

        assert len(tokens) == 1
        assert tokens[0].access_token == "new-token"
        assert tokens[0].cloud_id == "new-cloud-id"

    @pytest.mark.asyncio
    async def test_oauth_service_exchange_code_calculates_expiration(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should set expires_at correctly from expires_in."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            token_response = MagicMock()
            token_response.json.return_value = {
                "access_token": "test-token",
                "expires_in": 3600,  # 1 hour
            }
            token_response.raise_for_status = MagicMock()

            resources_response = MagicMock()
            resources_response.json.return_value = [
                {"id": "cloud-id", "url": "https://test.atlassian.net"}
            ]
            resources_response.raise_for_status = MagicMock()

            mock_client.post.return_value = token_response
            mock_client.get.return_value = resources_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"
                mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

                before = datetime.now(timezone.utc)
                token = await OAuthService.exchange_jira_code_for_token(
                    "code", db_session
                )
                after = datetime.now(timezone.utc)

        # expires_at should be ~1 hour from now
        assert token.expires_at is not None
        expected_min = before + timedelta(seconds=3600)
        expected_max = after + timedelta(seconds=3600)
        assert expected_min <= token.expires_at <= expected_max

    @pytest.mark.asyncio
    async def test_oauth_service_exchange_code_handles_api_failure(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should raise exception on API error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock API error response
            token_response = MagicMock()
            token_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Token request failed",
                request=MagicMock(),
                response=MagicMock(status_code=400),
            )

            mock_client.post.return_value = token_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"
                mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

                with pytest.raises(httpx.HTTPStatusError):
                    await OAuthService.exchange_jira_code_for_token(
                        "invalid-code", db_session
                    )

    @pytest.mark.asyncio
    async def test_oauth_service_exchange_code_missing_refresh_token_handled(
        self, db_session: AsyncSession
    ) -> None:
        """exchange_code should handle missing refresh_token in response."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Response without refresh_token
            token_response = MagicMock()
            token_response.json.return_value = {
                "access_token": "access-only-token",
                "expires_in": 3600,
            }
            token_response.raise_for_status = MagicMock()

            resources_response = MagicMock()
            resources_response.json.return_value = [
                {"id": "cloud-id", "url": "https://test.atlassian.net"}
            ]
            resources_response.raise_for_status = MagicMock()

            mock_client.post.return_value = token_response
            mock_client.get.return_value = resources_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"
                mock_settings.jira_oauth_redirect_uri = "http://localhost/callback"

                token = await OAuthService.exchange_jira_code_for_token(
                    "code", db_session
                )

            # Should handle missing refresh_token gracefully
            assert token.access_token == "access-only-token"
            assert token.refresh_token is None


class TestTokenRefresh:
    """Test OAuth token refresh functionality."""

    @pytest.mark.asyncio
    async def test_oauth_service_refresh_token_calls_atlassian_endpoint(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_token should POST with refresh_token grant."""
        # Create existing token with refresh token
        existing_token = OAuthTokenDB(
            provider="jira",
            access_token="old-access-token",
            refresh_token="valid-refresh-token",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db_session.add(existing_token)
        await db_session.commit()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            refresh_response = MagicMock()
            refresh_response.json.return_value = {
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
            refresh_response.raise_for_status = MagicMock()

            mock_client.post.return_value = refresh_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"

                await OAuthService.refresh_jira_token(db_session)

            # Verify refresh endpoint was called correctly
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == OAuthService.JIRA_TOKEN_URL
            assert call_args[1]["data"]["grant_type"] == "refresh_token"
            assert call_args[1]["data"]["refresh_token"] == "valid-refresh-token"

    @pytest.mark.asyncio
    async def test_oauth_service_refresh_token_updates_existing_record(
        self, db_session: AsyncSession
    ) -> None:
        """refresh_token should update existing token not create new one."""
        # Create existing token
        existing_token = OAuthTokenDB(
            provider="jira",
            access_token="old-token",
            refresh_token="refresh-token",
            cloud_id="cloud-id-123",
        )
        db_session.add(existing_token)
        await db_session.commit()
        token_id = existing_token.id

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            refresh_response = MagicMock()
            refresh_response.json.return_value = {
                "access_token": "refreshed-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
            }
            refresh_response.raise_for_status = MagicMock()

            mock_client.post.return_value = refresh_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"

                refreshed = await OAuthService.refresh_jira_token(db_session)

        # Should be same record (same ID)
        assert refreshed.id == token_id
        assert refreshed.access_token == "refreshed-token"

        # Verify only one token exists
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
        # Create token without refresh_token
        token_without_refresh = OAuthTokenDB(
            provider="jira",
            access_token="access-token-only",
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
        # Create fresh token (expires in 30 minutes)
        fresh_token = OAuthTokenDB(
            provider="jira",
            access_token="fresh-token",
            refresh_token="refresh-token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db_session.add(fresh_token)
        await db_session.commit()

        token = await OAuthService.get_valid_jira_token(db_session)

        assert token == "fresh-token"

    @pytest.mark.asyncio
    async def test_oauth_service_get_valid_token_refreshes_when_expired(
        self, db_session: AsyncSession
    ) -> None:
        """get_valid_token should auto-refresh if expired."""
        # Create expired token
        expired_token = OAuthTokenDB(
            provider="jira",
            access_token="expired-token",
            refresh_token="valid-refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db_session.add(expired_token)
        await db_session.commit()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            refresh_response = MagicMock()
            refresh_response.json.return_value = {
                "access_token": "refreshed-token",
                "expires_in": 3600,
            }
            refresh_response.raise_for_status = MagicMock()

            mock_client.post.return_value = refresh_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"

                token = await OAuthService.get_valid_jira_token(db_session)

        assert token == "refreshed-token"

    @pytest.mark.asyncio
    async def test_oauth_service_get_valid_token_refreshes_within_5min_buffer(
        self, db_session: AsyncSession
    ) -> None:
        """get_valid_token should refresh 5 minutes before expiry."""
        # Create token expiring in 3 minutes (within 5-minute buffer)
        soon_to_expire = OAuthTokenDB(
            provider="jira",
            access_token="about-to-expire",
            refresh_token="refresh-token",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=3),
        )
        db_session.add(soon_to_expire)
        await db_session.commit()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            refresh_response = MagicMock()
            refresh_response.json.return_value = {
                "access_token": "pre-emptively-refreshed",
                "expires_in": 3600,
            }
            refresh_response.raise_for_status = MagicMock()

            mock_client.post.return_value = refresh_response

            with patch("app.services.oauth_service.settings") as mock_settings:
                mock_settings.jira_oauth_client_id = "test-client"
                mock_settings.jira_oauth_client_secret = "test-secret"

                token = await OAuthService.get_valid_jira_token(db_session)

        # Should have refreshed even though not technically expired
        assert token == "pre-emptively-refreshed"

    @pytest.mark.asyncio
    async def test_oauth_service_get_valid_token_returns_none_when_missing(
        self, db_session: AsyncSession
    ) -> None:
        """get_valid_token should return None when no token exists."""
        token = await OAuthService.get_valid_jira_token(db_session)

        assert token is None
