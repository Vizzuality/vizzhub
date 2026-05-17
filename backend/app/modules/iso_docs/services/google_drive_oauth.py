"""Google Drive OAuth service for ISO Docs export."""

from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.models.oauth import OAuthTokenDB
from app.core.token_encryption import decrypt_token, encrypt_token

logger = structlog.get_logger()

PROVIDER = "google_drive"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "https://www.googleapis.com/auth/drive"


class GoogleDriveOAuth:
    @staticmethod
    def _get_client_credentials() -> tuple[str, str]:
        settings = get_settings()
        client_id = settings.google_workspace_client_id or settings.google_client_id
        client_secret = settings.google_workspace_client_secret or settings.google_client_secret
        return client_id, client_secret

    @staticmethod
    async def _get_token(db: AsyncSession) -> OAuthTokenDB | None:
        result = await db.execute(select(OAuthTokenDB).where(OAuthTokenDB.provider == PROVIDER))
        return result.scalar_one_or_none()

    @staticmethod
    def get_authorization_url(state: str, redirect_uri: str) -> str:
        client_id, _ = GoogleDriveOAuth._get_client_credentials()
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent select_account",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_token(
        code: str, redirect_uri: str, db: AsyncSession
    ) -> OAuthTokenDB:
        client_id, client_secret = GoogleDriveOAuth._get_client_credentials()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

        expires_in = token_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        existing = await GoogleDriveOAuth._get_token(db)
        if existing:
            await db.delete(existing)

        oauth_token = OAuthTokenDB(
            provider=PROVIDER,
            access_token=encrypt_token(token_data["access_token"]),
            refresh_token=(
                encrypt_token(token_data["refresh_token"])
                if token_data.get("refresh_token")
                else None
            ),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope"),
        )
        db.add(oauth_token)
        await db.flush()
        await db.refresh(oauth_token)

        logger.info("google_drive_token_stored")
        return oauth_token

    @staticmethod
    async def refresh_token(db: AsyncSession) -> OAuthTokenDB | None:
        token = await GoogleDriveOAuth._get_token(db)
        if not token or not token.refresh_token:
            return None

        client_id, client_secret = GoogleDriveOAuth._get_client_credentials()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": decrypt_token(token.refresh_token),
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

        expires_in = token_data.get("expires_in")
        if expires_in:
            token.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        token.access_token = encrypt_token(token_data["access_token"])
        if "refresh_token" in token_data:
            token.refresh_token = encrypt_token(token_data["refresh_token"])

        await db.flush()
        await db.refresh(token)

        logger.info("google_drive_token_refreshed")
        return token

    @staticmethod
    async def get_valid_token(db: AsyncSession) -> str | None:
        token = await GoogleDriveOAuth._get_token(db)
        if not token:
            return None

        if token.expires_at:
            buffer = timedelta(minutes=5)
            if token.expires_at - buffer <= datetime.now(UTC):
                refreshed = await GoogleDriveOAuth.refresh_token(db)
                if refreshed:
                    return decrypt_token(refreshed.access_token)
                return None

        return decrypt_token(token.access_token)

    @staticmethod
    async def disconnect(db: AsyncSession) -> None:
        token = await GoogleDriveOAuth._get_token(db)
        if token:
            await db.delete(token)
            await db.flush()
            logger.info("google_drive_disconnected")

    @staticmethod
    async def get_status(db: AsyncSession) -> dict[str, Any]:
        token = await GoogleDriveOAuth._get_token(db)
        if not token:
            return {"connected": False}
        return {"connected": True}
