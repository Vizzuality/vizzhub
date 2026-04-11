"""Google OAuth callback — completes the SSO flow for MCP authentication."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import structlog
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from app.core.models.mcp_oauth import MCPOAuthCodeDB
from app.core.models.user import UserDB
from app.core.permissions.resolver import resolve_permissions

logger = structlog.get_logger()

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_CODE_TTL_SECONDS = 60


async def _exchange_google_code(
    google_code: str,
    google_client_id: str,
    google_client_secret: str,
    redirect_uri: str,
) -> tuple[int, dict]:
    """Exchange a Google auth code for tokens. Returns (status_code, json_body)."""
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": google_code,
                "client_id": google_client_id,
                "client_secret": google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    return resp.status_code, resp.json()


def _error_html(message: str) -> HTMLResponse:
    """Return a minimal error page instead of redirecting to an unknown URL."""
    return HTMLResponse(
        content=(
            "<!DOCTYPE html><html><head><title>Authentication Error</title></head>"
            f"<body><h2>Authentication Error</h2><p>{message}</p></body></html>"
        ),
        status_code=400,
    )


def build_google_oauth_callback(
    session_maker: async_sessionmaker,
    google_client_id: str,
    google_client_secret: str,
    allowed_google_domain: str,
    base_url: str,
):
    """Return a Starlette endpoint closed over the required configuration.

    The returned coroutine is suitable for ``Route("/oauth/callback", ...)``.
    """
    base_url = base_url.rstrip("/")
    callback_redirect_uri = f"{base_url}/oauth/callback"

    async def google_oauth_callback(request: Request) -> RedirectResponse | HTMLResponse:
        google_code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not google_code or not state:
            logger.warning("mcp_oauth_callback_missing_params")
            return _error_html("Missing required parameters.")

        async with session_maker() as session:
            result = await session.execute(
                select(MCPOAuthCodeDB).where(MCPOAuthCodeDB.code == state)
            )
            original = result.scalar_one_or_none()

            if original is None:
                logger.warning("mcp_oauth_callback_invalid_state", state=state[:8] + "...")
                return _error_html("Invalid or expired session.")

            if original.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                logger.warning("mcp_oauth_callback_expired_state", state=state[:8] + "...")
                await session.delete(original)
                await session.commit()
                return _error_html("Session expired. Please try again.")

            # Exchange Google auth code for tokens
            status_code, tokens = await _exchange_google_code(
                google_code, google_client_id, google_client_secret, callback_redirect_uri,
            )

            if status_code != 200:
                logger.warning(
                    "mcp_oauth_callback_google_token_failed",
                    status=status_code,
                )
                return _error_html("Failed to authenticate with Google.")

            raw_id_token = tokens.get("id_token")
            if not raw_id_token:
                logger.warning("mcp_oauth_callback_no_id_token")
                return _error_html("Google did not return an ID token.")

            # Verify ID token
            try:
                idinfo = id_token.verify_oauth2_token(
                    raw_id_token,
                    google_requests.Request(),
                    google_client_id,
                )
            except ValueError:
                logger.warning("mcp_oauth_callback_id_token_invalid")
                return _error_html("Invalid Google ID token.")

            email = idinfo.get("email", "").lower()
            if not email:
                return _error_html("Google did not provide an email address.")

            # Domain restriction
            domain = email.split("@")[-1]
            if domain != allowed_google_domain:
                logger.warning("mcp_oauth_callback_domain_rejected", email=email)
                return _error_html("Unauthorized domain.")

            # Look up VizzHub user
            user_result = await session.execute(
                select(UserDB).where(UserDB.email == email)
            )
            user = user_result.scalar_one_or_none()

            if user is None:
                logger.warning("mcp_oauth_callback_user_not_found", email=email)
                return _error_html("User not found. Please log in to VizzHub first.")

            if not user.active:
                logger.warning("mcp_oauth_callback_user_inactive", email=email)
                return _error_html("Account deactivated. Contact an administrator.")

            # Resolve roles and permissions
            roles, permissions = await resolve_permissions(session, str(user.id))

            # Create new auth code with user info
            new_code = secrets.token_urlsafe(32)
            new_row = MCPOAuthCodeDB(
                code=new_code,
                client_id=original.client_id,
                code_challenge=original.code_challenge,
                redirect_uri=original.redirect_uri,
                redirect_uri_provided_explicitly=original.redirect_uri_provided_explicitly,
                scopes=original.scopes,
                resource=original.resource,
                mcp_state=original.mcp_state,
                user_id=user.id,
                user_email=email,
                user_roles=roles,
                user_permissions=permissions,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=AUTH_CODE_TTL_SECONDS),
            )
            session.add(new_row)
            await session.delete(original)
            await session.commit()

        # Redirect back to the MCP client
        redirect_params: dict[str, str] = {"code": new_code}
        if new_row.mcp_state:
            redirect_params["state"] = new_row.mcp_state

        redirect_url = f"{original.redirect_uri}?{urlencode(redirect_params)}"

        logger.info(
            "mcp_oauth_callback_success",
            email=email,
            client_id=original.client_id,
        )
        return RedirectResponse(url=redirect_url, status_code=302)

    return google_oauth_callback
