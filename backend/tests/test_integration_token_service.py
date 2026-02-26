"""Tests for IntegrationTokenService."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import decrypt_token, encrypt_token
from app.models.integration_setting import IntegrationSettingDB
from app.models.oauth import OAuthTokenDB
from app.services.integration_token_service import IntegrationTokenService


class TestGetToken:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_token(self, db_session: AsyncSession) -> None:
        result = await IntegrationTokenService.get_token(db_session, "github")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_decrypted_token(self, db_session: AsyncSession) -> None:
        token = OAuthTokenDB(
            provider="github",
            access_token=encrypt_token("ghp_secret123"),
            token_type="Bearer",
        )
        db_session.add(token)
        await db_session.flush()

        result = await IntegrationTokenService.get_token(db_session, "github")
        assert result == "ghp_secret123"


class TestSaveToken:
    @pytest.mark.asyncio
    async def test_saves_encrypted_token(self, db_session: AsyncSession) -> None:
        record = await IntegrationTokenService.save_token(
            db_session,
            provider="github",
            token="ghp_plaintext",
            token_type="pat",
        )

        assert record.provider == "github"
        assert record.token_type == "pat"
        assert record.access_token != "ghp_plaintext"
        assert decrypt_token(record.access_token) == "ghp_plaintext"
        assert record.expires_at is None

    @pytest.mark.asyncio
    async def test_replaces_existing_token(self, db_session: AsyncSession) -> None:
        await IntegrationTokenService.save_token(
            db_session,
            provider="github",
            token="first_token",
            token_type="pat",
        )
        await IntegrationTokenService.save_token(
            db_session,
            provider="github",
            token="second_token",
            token_type="pat",
        )

        result = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "github")
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert decrypt_token(rows[0].access_token) == "second_token"

    @pytest.mark.asyncio
    async def test_saves_with_expiry(self, db_session: AsyncSession) -> None:
        before = datetime.now(timezone.utc)
        record = await IntegrationTokenService.save_token(
            db_session,
            provider="github",
            token="ghp_expiring",
            token_type="pat",
            expires_in_days=90,
        )
        after = datetime.now(timezone.utc)

        assert record.expires_at is not None
        expected_min = before + timedelta(days=90)
        expected_max = after + timedelta(days=90)
        assert expected_min <= record.expires_at <= expected_max


class TestDeleteToken:
    @pytest.mark.asyncio
    async def test_deletes_existing_token(self, db_session: AsyncSession) -> None:
        token = OAuthTokenDB(
            provider="github",
            access_token=encrypt_token("to_delete"),
            token_type="pat",
        )
        db_session.add(token)
        await db_session.flush()

        result = await IntegrationTokenService.delete_token(db_session, "github")
        assert result is True

        check = await db_session.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "github")
        )
        assert check.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent(
        self, db_session: AsyncSession
    ) -> None:
        result = await IntegrationTokenService.delete_token(db_session, "nonexistent")
        assert result is False


class TestGetSetting:
    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self, db_session: AsyncSession) -> None:
        result = await IntegrationTokenService.get_setting(
            db_session, "slack", "channel_id"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_value_when_exists(self, db_session: AsyncSession) -> None:
        setting = IntegrationSettingDB(
            provider="slack",
            key="channel_id",
            value="C12345",
        )
        db_session.add(setting)
        await db_session.flush()

        result = await IntegrationTokenService.get_setting(
            db_session, "slack", "channel_id"
        )
        assert result == "C12345"


class TestSetSetting:
    @pytest.mark.asyncio
    async def test_creates_new_setting(self, db_session: AsyncSession) -> None:
        await IntegrationTokenService.set_setting(
            db_session, "slack", "webhook_url", "https://hooks.slack.com/xxx"
        )

        result = await db_session.execute(
            select(IntegrationSettingDB).where(
                IntegrationSettingDB.provider == "slack",
                IntegrationSettingDB.key == "webhook_url",
            )
        )
        record = result.scalar_one()
        assert record.value == "https://hooks.slack.com/xxx"

    @pytest.mark.asyncio
    async def test_updates_existing_setting(self, db_session: AsyncSession) -> None:
        await IntegrationTokenService.set_setting(
            db_session, "slack", "channel_id", "C_old"
        )
        await IntegrationTokenService.set_setting(
            db_session, "slack", "channel_id", "C_new"
        )

        result = await db_session.execute(
            select(IntegrationSettingDB).where(
                IntegrationSettingDB.provider == "slack",
                IntegrationSettingDB.key == "channel_id",
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1
        assert rows[0].value == "C_new"


class TestGetProviderStatus:
    @pytest.mark.asyncio
    async def test_returns_disconnected_when_no_token(
        self, db_session: AsyncSession
    ) -> None:
        status = await IntegrationTokenService.get_provider_status(db_session, "github")
        assert status == {
            "connected": False,
            "expires_at": None,
            "token_type": None,
            "site_url": None,
            "created_at": None,
        }

    @pytest.mark.asyncio
    async def test_returns_connected_status_with_metadata(
        self, db_session: AsyncSession
    ) -> None:
        expires = datetime.now(timezone.utc) + timedelta(days=90)
        token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token("jira_token"),
            token_type="Bearer",
            expires_at=expires,
            site_url="https://mysite.atlassian.net",
        )
        db_session.add(token)
        await db_session.flush()

        status = await IntegrationTokenService.get_provider_status(db_session, "jira")
        assert status["connected"] is True
        assert status["expires_at"] is not None
        assert status["token_type"] == "Bearer"
        assert status["site_url"] == "https://mysite.atlassian.net"
        assert status["created_at"] is not None
