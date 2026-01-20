"""OAuth 2.0 service for Jira and GitHub authentication."""

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.oauth import OAuthTokenDB

settings = get_settings()


class OAuthService:
    """Handles OAuth 2.0 flows for external services."""

    JIRA_AUTH_URL = "https://auth.atlassian.com/authorize"
    JIRA_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
    JIRA_ACCESSIBLE_RESOURCES_URL = (
        "https://api.atlassian.com/oauth/token/accessible-resources"
    )

    @staticmethod
    def get_jira_authorization_url(state: str | None = None) -> str:
        """Generate Jira OAuth authorization URL."""
        params = {
            "audience": "api.atlassian.com",
            "client_id": settings.jira_oauth_client_id,
            "scope": settings.jira_oauth_scopes,
            "redirect_uri": settings.jira_oauth_redirect_uri,
            "response_type": "code",
            "prompt": "consent",
        }
        if state:
            params["state"] = state

        return f"{OAuthService.JIRA_AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_jira_code_for_token(
        code: str, db: AsyncSession
    ) -> OAuthTokenDB:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
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

        # Get accessible resources (Jira sites)
        access_token = token_data["access_token"]
        async with httpx.AsyncClient() as client:
            resources_response = await client.get(
                OAuthService.JIRA_ACCESSIBLE_RESOURCES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resources_response.raise_for_status()
            resources = resources_response.json()

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
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scope=token_data.get("scope"),
            cloud_id=cloud_id,
            site_url=site_url,
        )

        db.add(oauth_token)
        await db.commit()
        await db.refresh(oauth_token)

        return oauth_token

    @staticmethod
    async def refresh_jira_token(db: AsyncSession) -> OAuthTokenDB | None:
        """Refresh the Jira access token using refresh token."""
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        token = result.scalar_one_or_none()

        if not token or not token.refresh_token:
            return None

        async with httpx.AsyncClient() as client:
            response = await client.post(
                OAuthService.JIRA_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": settings.jira_oauth_client_id,
                    "client_secret": settings.jira_oauth_client_secret,
                    "refresh_token": token.refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()

        # Update token
        expires_in = token_data.get("expires_in")
        if expires_in:
            token.expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in
            )

        token.access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            token.refresh_token = token_data["refresh_token"]
        token.token_type = token_data.get("token_type", "Bearer")
        token.scope = token_data.get("scope")

        await db.commit()
        await db.refresh(token)

        return token

    @staticmethod
    async def get_valid_jira_token(db: AsyncSession) -> str | None:
        """Get a valid Jira access token, refreshing if necessary."""
        result = await db.execute(
            select(OAuthTokenDB).where(OAuthTokenDB.provider == "jira")
        )
        token = result.scalar_one_or_none()

        if not token:
            return None

        # Check if token is expired or about to expire (5 min buffer)
        if token.expires_at:
            now = datetime.now(timezone.utc)
            buffer = timedelta(minutes=5)
            if token.expires_at - buffer <= now:
                # Token expired or about to expire, refresh it
                refreshed_token = await OAuthService.refresh_jira_token(db)
                if refreshed_token:
                    return refreshed_token.access_token
                return None

        return token.access_token

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
