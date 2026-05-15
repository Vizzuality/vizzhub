"""OAuth 2.0 service for Jira and GitHub authentication."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.core.models.oauth import OAuthTokenDB
from app.core.token_encryption import decrypt_token, encrypt_token

settings = get_settings()
logger = structlog.get_logger()

# Concurrent callers refreshing the same provider's token would otherwise
# issue duplicate refresh calls to Jira; the second one races on a now-stale
# refresh_token and lands the integration in an invalid_grant state.
_REFRESH_LOCKS: dict[str, asyncio.Lock] = {}
TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)


def _refresh_lock(provider: str) -> asyncio.Lock:
    lock = _REFRESH_LOCKS.get(provider)
    if lock is None:
        lock = asyncio.Lock()
        _REFRESH_LOCKS[provider] = lock
    return lock


class OAuthService:
    """Handles OAuth 2.0 flows for external services."""

    JIRA_AUTH_URL = "https://auth.atlassian.com/authorize"
    JIRA_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
    JIRA_ACCESSIBLE_RESOURCES_URL = (
        "https://api.atlassian.com/oauth/token/accessible-resources"
    )
    JIRA_REQUIRED_SCOPES = (
        "read:jira-work read:jira-user "
        "read:issue-details:jira read:user:jira read:project:jira "
        "read:board-scope:jira-software read:sprint:jira-software "
        "offline_access"
    )

    @staticmethod
    def get_jira_authorization_url(state: str | None = None) -> str:
        """Generate Jira OAuth authorization URL."""
        params = {
            "audience": "api.atlassian.com",
            "client_id": settings.jira_oauth_client_id,
            "scope": OAuthService.JIRA_REQUIRED_SCOPES,
            "redirect_uri": settings.jira_oauth_redirect_uri,
            "response_type": "code",
            "prompt": "consent",
        }
        if state:
            params["state"] = state

        return f"{OAuthService.JIRA_AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_jira_code_for_token(code: str, db: AsyncSession) -> OAuthTokenDB:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(
                    OAuthService.JIRA_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": settings.jira_oauth_client_id,
                        "client_secret": settings.jira_oauth_client_secret,
                        "code": code,
                        "redirect_uri": settings.jira_oauth_redirect_uri,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                token_data = response.json()
            except httpx.HTTPError:
                logger.exception("jira_token_exchange_failed")
                raise

            access_token = token_data["access_token"]
            try:
                resources_response = await client.get(
                    OAuthService.JIRA_ACCESSIBLE_RESOURCES_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resources_response.raise_for_status()
                resources = resources_response.json()
            except httpx.HTTPError:
                logger.exception("jira_accessible_resources_failed")
                raise

        # Use the first accessible resource
        cloud_id = resources[0]["id"] if resources else None
        site_url = resources[0]["url"] if resources else None

        # Calculate expiration
        expires_in = token_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # Delete existing Jira token (single instance)
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        existing = result.scalar_one_or_none()
        if existing:
            await db.delete(existing)

        # Create new token
        oauth_token = OAuthTokenDB(
            provider="jira",
            access_token=encrypt_token(token_data["access_token"]),
            refresh_token=(
                encrypt_token(token_data["refresh_token"])
                if token_data.get("refresh_token")
                else None
            ),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope"),
            cloud_id=cloud_id,
            site_url=site_url,
        )

        db.add(oauth_token)
        await db.flush()
        await db.refresh(oauth_token)

        logger.info("jira_token_exchanged", cloud_id=cloud_id)

        return oauth_token

    @staticmethod
    async def refresh_jira_token(db: AsyncSession) -> OAuthTokenDB | None:
        """Refresh the Jira access token using refresh token.

        Persists the updated token via a dedicated writable session so
        this works even when the caller's session is read-only (e.g. MCP).
        Concurrent refreshers serialize on an asyncio lock and re-check
        expiry inside the critical section so only one Jira call fires.
        """
        async with _refresh_lock("jira"):
            result = await db.execute(
                select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
            )
            token = result.scalar_one_or_none()

            if not token or not token.refresh_token:
                return None

            if token.expires_at:
                now = datetime.now(timezone.utc)
                if token.expires_at - TOKEN_EXPIRY_BUFFER > now:
                    logger.info("jira_token_refresh_skipped_already_fresh")
                    return token

            token_id = token.id

            async with httpx.AsyncClient(timeout=20.0) as client:
                try:
                    response = await client.post(
                        OAuthService.JIRA_TOKEN_URL,
                        data={
                            "grant_type": "refresh_token",
                            "client_id": settings.jira_oauth_client_id,
                            "client_secret": settings.jira_oauth_client_secret,
                            "refresh_token": decrypt_token(token.refresh_token),
                        },
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                    response.raise_for_status()
                    token_data = response.json()
                except httpx.HTTPError:
                    logger.exception("jira_token_refresh_failed")
                    raise

            db_url = get_settings().database_url
            write_engine = create_async_engine(db_url)
            write_maker = async_sessionmaker(
                write_engine, class_=AsyncSession, expire_on_commit=False,
            )
            try:
                async with write_maker() as write_session:
                    result = await write_session.execute(
                        select(OAuthTokenDB).where(OAuthTokenDB.id == token_id)
                    )
                    writable_token = result.scalar_one()

                    expires_in = token_data.get("expires_in")
                    if expires_in:
                        writable_token.expires_at = datetime.now(
                            timezone.utc
                        ) + timedelta(seconds=expires_in)

                    writable_token.access_token = encrypt_token(
                        token_data["access_token"]
                    )
                    if "refresh_token" in token_data:
                        writable_token.refresh_token = encrypt_token(
                            token_data["refresh_token"]
                        )
                    writable_token.token_type = token_data.get("token_type", "Bearer")
                    writable_token.scope = token_data.get("scope")

                    await write_session.commit()
                    await write_session.refresh(writable_token)
                    write_session.expunge(writable_token)
                    logger.info("jira_token_refreshed", token_id=str(token_id))
                    return writable_token
            finally:
                await write_engine.dispose()

    @staticmethod
    async def get_valid_jira_token(db: AsyncSession) -> str | None:
        """Get a valid Jira access token, refreshing if necessary."""
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        token = result.scalar_one_or_none()

        if not token:
            return None

        if token.expires_at:
            now = datetime.now(timezone.utc)
            if token.expires_at - TOKEN_EXPIRY_BUFFER <= now:
                refreshed_token = await OAuthService.refresh_jira_token(db)
                if refreshed_token:
                    return decrypt_token(refreshed_token.access_token)
                return None

        return decrypt_token(token.access_token)

    @staticmethod
    async def get_jira_site_info(db: AsyncSession) -> dict[str, Any] | None:
        """Get Jira site information from stored OAuth token."""
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        token = result.scalar_one_or_none()

        if not token:
            return None

        return {"cloud_id": token.cloud_id, "site_url": token.site_url}
