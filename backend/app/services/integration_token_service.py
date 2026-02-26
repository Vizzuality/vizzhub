"""Shared service for reading/writing integration tokens and settings."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.token_encryption import decrypt_token, encrypt_token
from app.models.integration_setting import IntegrationSettingDB
from app.models.oauth import OAuthTokenDB


class IntegrationTokenService:
    """Central abstraction for integration token and setting operations."""

    @staticmethod
    async def get_token(db: AsyncSession, provider: str) -> str | None:
        """Get decrypted token for provider. Returns None if not found."""
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == provider)
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return decrypt_token(record.access_token)

    @staticmethod
    async def get_token_record(db: AsyncSession, provider: str) -> OAuthTokenDB | None:
        """Get raw OAuthTokenDB record (for metadata like expires_at)."""
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == provider)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def save_token(
        db: AsyncSession,
        *,
        provider: str,
        token: str,
        token_type: str,
        expires_in_days: int | None = None,
    ) -> OAuthTokenDB:
        """Delete existing token for provider, encrypt new one, save. Returns record."""
        await db.execute(delete(OAuthTokenDB).where(OAuthTokenDB.provider == provider))

        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        record = OAuthTokenDB(
            provider=provider,
            access_token=encrypt_token(token),
            token_type=token_type,
            expires_at=expires_at,
        )
        db.add(record)
        await db.flush()
        await db.refresh(record)
        return record

    @staticmethod
    async def delete_token(db: AsyncSession, provider: str) -> bool:
        """Delete token for provider. Returns True if deleted, False if not found."""
        result = await db.execute(
            delete(OAuthTokenDB).where(OAuthTokenDB.provider == provider)
        )
        return result.rowcount > 0

    @staticmethod
    async def get_setting(db: AsyncSession, provider: str, key: str) -> str | None:
        """Get setting value. Returns None if not found."""
        result = await db.execute(
            select(IntegrationSettingDB).where(
                IntegrationSettingDB.provider == provider,
                IntegrationSettingDB.key == key,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        return record.value

    @staticmethod
    async def set_setting(
        db: AsyncSession, provider: str, key: str, value: str
    ) -> None:
        """Create or update setting (upsert)."""
        result = await db.execute(
            select(IntegrationSettingDB).where(
                IntegrationSettingDB.provider == provider,
                IntegrationSettingDB.key == key,
            )
        )
        record = result.scalar_one_or_none()
        if record is not None:
            record.value = value
        else:
            record = IntegrationSettingDB(
                provider=provider,
                key=key,
                value=value,
            )
            db.add(record)
        await db.flush()

    @staticmethod
    async def get_provider_status(db: AsyncSession, provider: str) -> dict:
        """Return status dict with: connected, expires_at, token_type, site_url, created_at."""
        record = await IntegrationTokenService.get_token_record(db, provider)
        if record is None:
            return {
                "connected": False,
                "expires_at": None,
                "token_type": None,
                "site_url": None,
                "created_at": None,
            }
        return {
            "connected": True,
            "expires_at": record.expires_at,
            "token_type": record.token_type,
            "site_url": record.site_url,
            "created_at": record.created_at,
        }
