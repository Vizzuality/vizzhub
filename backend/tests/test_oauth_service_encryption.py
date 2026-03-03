"""Tests that Jira OAuth service encrypts tokens at rest."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import decrypt_token
from app.core.models.oauth import OAuthTokenDB
from app.services.oauth_service import OAuthService


class TestJiraTokenEncryption:
    """Verify Jira tokens are encrypted before DB storage."""

    @pytest.mark.asyncio
    async def test_exchange_code_encrypts_tokens(
        self, db_session: AsyncSession
    ) -> None:
        """Tokens from code exchange should be stored encrypted."""
        token_response = MagicMock()
        token_response.json.return_value = {
            "access_token": "jira-access-plain",
            "refresh_token": "jira-refresh-plain",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "read:jira-work",
        }
        token_response.raise_for_status = MagicMock()

        resources_response = MagicMock()
        resources_response.json.return_value = [
            {"id": "cloud-123", "url": "https://test.atlassian.net"}
        ]
        resources_response.raise_for_status = MagicMock()

        mock_http = MagicMock()
        mock_http.post = AsyncMock(return_value=token_response)
        mock_http.get = AsyncMock(return_value=resources_response)

        with patch("app.services.oauth_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await OAuthService.exchange_jira_code_for_token("auth-code", db_session)

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        token = result.scalar_one()

        assert token.access_token != "jira-access-plain"
        assert token.refresh_token != "jira-refresh-plain"
        assert decrypt_token(token.access_token) == "jira-access-plain"
        assert decrypt_token(token.refresh_token) == "jira-refresh-plain"

    @pytest.mark.asyncio
    async def test_get_valid_token_decrypts(self, db_session: AsyncSession) -> None:
        """get_valid_jira_token should return decrypted access token."""
        from app.core.token_encryption import encrypt_token

        token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("decrypted-jira-token"),
            refresh_token=encrypt_token("refresh"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(token)
        await db_session.flush()

        result = await OAuthService.get_valid_jira_token(db_session)
        assert result == "decrypted-jira-token"

    @pytest.mark.asyncio
    async def test_refresh_encrypts_new_tokens(self, db_session: AsyncSession) -> None:
        """Refreshed tokens should be stored encrypted."""
        from app.core.token_encryption import encrypt_token

        existing = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("old-access"),
            refresh_token=encrypt_token("old-refresh"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(existing)
        await db_session.flush()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-jira-access",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = MagicMock()
        mock_http.post = AsyncMock(return_value=mock_response)

        with patch("app.services.oauth_service.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await OAuthService.refresh_jira_token(db_session)

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        token = result.scalar_one()
        assert decrypt_token(token.access_token) == "new-jira-access"
        assert decrypt_token(token.refresh_token) == "old-refresh"
