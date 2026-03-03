"""Tests that Google Workspace OAuth service encrypts tokens at rest."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import decrypt_token
from app.core.models.oauth import OAuthTokenDB
from app.modules.iso.services.google_workspace_oauth import (
    PROVIDER,
    GoogleWorkspaceOAuth,
)


class TestGoogleWorkspaceTokenEncryption:
    """Verify tokens are encrypted before DB storage."""

    @pytest.mark.asyncio
    async def test_exchange_code_encrypts_tokens(
        self, db_session: AsyncSession
    ) -> None:
        """Tokens from code exchange should be stored encrypted."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "plaintext-access-token",
            "refresh_token": "plaintext-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "test-scope",
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch(
                "app.modules.iso.services.google_workspace_oauth.httpx.AsyncClient"
            ) as mock_client,
            patch(
                "app.modules.iso.services.google_workspace_oauth.get_settings"
            ) as mock_settings,
        ):
            mock_settings.return_value.google_workspace_client_id = "cid"
            mock_settings.return_value.google_workspace_client_secret = "cs"
            mock_settings.return_value.google_client_id = ""
            mock_settings.return_value.google_client_secret = ""
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await GoogleWorkspaceOAuth.exchange_code_for_token(
                code="auth-code",
                domain="test.com",
                redirect_uri="http://localhost/callback",
                db=db_session,
            )

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER)
        )
        token = result.scalar_one()

        assert token.access_token != "plaintext-access-token"
        assert token.refresh_token != "plaintext-refresh-token"
        assert decrypt_token(token.access_token) == "plaintext-access-token"
        assert decrypt_token(token.refresh_token) == "plaintext-refresh-token"

    @pytest.mark.asyncio
    async def test_get_valid_token_decrypts(self, db_session: AsyncSession) -> None:
        """get_valid_token should return decrypted access token."""
        from app.core.token_encryption import encrypt_token

        token = OAuthTokenDB(
            provider=PROVIDER,
            access_token=encrypt_token("decrypted-access-token"),
            refresh_token=encrypt_token("decrypted-refresh-token"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            site_url="test.com",
        )
        db_session.add(token)
        await db_session.flush()

        result = await GoogleWorkspaceOAuth.get_valid_token(db_session)
        assert result == "decrypted-access-token"

    @pytest.mark.asyncio
    async def test_refresh_token_encrypts_new_tokens(
        self, db_session: AsyncSession
    ) -> None:
        """Refreshed tokens should be stored encrypted."""
        from app.core.token_encryption import encrypt_token

        existing = OAuthTokenDB(
            provider=PROVIDER,
            access_token=encrypt_token("old-access"),
            refresh_token=encrypt_token("old-refresh"),
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            site_url="test.com",
        )
        db_session.add(existing)
        await db_session.flush()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch(
                "app.modules.iso.services.google_workspace_oauth.httpx.AsyncClient"
            ) as mock_client,
            patch(
                "app.modules.iso.services.google_workspace_oauth.get_settings"
            ) as mock_settings,
        ):
            mock_settings.return_value.google_workspace_client_id = "cid"
            mock_settings.return_value.google_workspace_client_secret = "cs"
            mock_settings.return_value.google_client_id = ""
            mock_settings.return_value.google_client_secret = ""
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            await GoogleWorkspaceOAuth.refresh_token(db_session)

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER)
        )
        token = result.scalar_one()
        assert decrypt_token(token.access_token) == "new-access-token"
        assert decrypt_token(token.refresh_token) == "old-refresh"
