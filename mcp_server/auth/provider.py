"""VizzHub OAuth provider — bridges MCP SDK auth to Google SSO."""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import structlog
from jose import JWTError, jwt
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.models.mcp_oauth import (
    MCPOAuthClientDB,
    MCPOAuthCodeDB,
    MCPOAuthRefreshTokenDB,
)

logger = structlog.get_logger()

ACCESS_TOKEN_TTL_HOURS = 2
REFRESH_TOKEN_TTL_DAYS = 30
AUTH_CODE_TTL_MINUTES = 5

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_SCOPES = "openid email profile"


class VizzHubOAuthProvider:
    """MCP ``OAuthAuthorizationServerProvider`` backed by PostgreSQL + Google SSO.

    Stores OAuth state (codes, refresh tokens) in the database and delegates
    user authentication to Google.  Access tokens are JWTs signed with the
    shared backend secret.
    """

    def __init__(
        self,
        session_maker: async_sessionmaker,
        jwt_secret: str,
        google_client_id: str,
        allowed_google_domain: str,
        base_url: str,
    ) -> None:
        self._session_maker = session_maker
        self._jwt_secret = jwt_secret
        self._google_client_id = google_client_id
        self._allowed_google_domain = allowed_google_domain
        self._base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Client registration
    # ------------------------------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        async with self._session_maker() as session:
            result = await session.execute(
                select(MCPOAuthClientDB).where(
                    MCPOAuthClientDB.client_id == client_id
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return OAuthClientInformationFull(**row.client_info)

    async def register_client(
        self, client_info: OAuthClientInformationFull
    ) -> OAuthClientInformationFull:
        """Stubbed — we pre-register clients manually.

        The MCP SDK requires this method to exist.  It inserts a row if called,
        but production flow relies on manual INSERT.
        """
        client_id = secrets.token_urlsafe(24)
        client_secret = secrets.token_urlsafe(48)

        full_info = client_info.model_copy(
            update={
                "client_id": client_id,
                "client_secret": client_secret,
                "client_id_issued_at": int(datetime.now(timezone.utc).timestamp()),
            }
        )

        async with self._session_maker() as session:
            session.add(
                MCPOAuthClientDB(
                    client_id=client_id,
                    client_secret=client_secret,
                    client_info=full_info.model_dump(mode="json"),
                )
            )
            await session.commit()

        logger.info("mcp_oauth_client_registered", client_id=client_id)
        return full_info

    # ------------------------------------------------------------------
    # Authorize
    # ------------------------------------------------------------------

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        code = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=AUTH_CODE_TTL_MINUTES
        )

        async with self._session_maker() as session:
            session.add(
                MCPOAuthCodeDB(
                    code=code,
                    client_id=client.client_id,
                    code_challenge=params.code_challenge,
                    redirect_uri=str(params.redirect_uri),
                    redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                    scopes=params.scopes,
                    resource=params.resource,
                    expires_at=expires_at,
                )
            )
            await session.commit()

        google_params = {
            "client_id": self._google_client_id,
            "redirect_uri": f"{self._base_url}/oauth/callback",
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "state": code,
            "hd": self._allowed_google_domain,
        }

        logger.info(
            "mcp_oauth_authorize_started",
            client_id=client.client_id,
            code=code[:8] + "...",
        )
        return f"{GOOGLE_AUTH_URL}?{urlencode(google_params)}"

    # ------------------------------------------------------------------
    # Authorization code
    # ------------------------------------------------------------------

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        async with self._session_maker() as session:
            result = await session.execute(
                select(MCPOAuthCodeDB).where(MCPOAuthCodeDB.code == authorization_code)
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None

        return AuthorizationCode(
            code=row.code,
            client_id=row.client_id,
            code_challenge=row.code_challenge,
            redirect_uri=row.redirect_uri,
            redirect_uri_provided_explicitly=row.redirect_uri_provided_explicitly,
            scopes=row.scopes or [],
            expires_at=row.expires_at.replace(tzinfo=timezone.utc).timestamp(),
            resource=row.resource,
        )

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        # Re-fetch the DB row for user info populated by the callback
        async with self._session_maker() as session:
            result = await session.execute(
                select(MCPOAuthCodeDB).where(
                    MCPOAuthCodeDB.code == authorization_code.code
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise ValueError("Authorization code not found")

            # PKCE verification
            code_verifier = getattr(authorization_code, "_code_verifier", None)
            if code_verifier:
                expected = (
                    base64.urlsafe_b64encode(
                        hashlib.sha256(code_verifier.encode()).digest()
                    )
                    .rstrip(b"=")
                    .decode()
                )
                if expected != row.code_challenge:
                    raise ValueError("PKCE verification failed")

            # Delete the consumed code
            await session.execute(
                delete(MCPOAuthCodeDB).where(
                    MCPOAuthCodeDB.code == authorization_code.code
                )
            )

            # Create JWT access token
            now = datetime.now(timezone.utc)
            payload = {
                "sub": str(row.user_id) if row.user_id else None,
                "email": row.user_email,
                "client_id": client.client_id,
                "roles": row.user_roles or [],
                "permissions": row.user_permissions or [],
                "scopes": row.scopes or [],
                "iss": "vizzhub",
                "aud": "vizzhub-mcp",
                "iat": now,
                "exp": now + timedelta(hours=ACCESS_TOKEN_TTL_HOURS),
            }
            access_token = jwt.encode(payload, self._jwt_secret, algorithm="HS256")

            # Create refresh token
            refresh_token_str = secrets.token_urlsafe(48)
            refresh_expires = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

            session.add(
                MCPOAuthRefreshTokenDB(
                    token=refresh_token_str,
                    client_id=client.client_id,
                    user_id=row.user_id,
                    user_email=row.user_email,
                    user_roles=row.user_roles,
                    user_permissions=row.user_permissions,
                    scopes=row.scopes,
                    resource=row.resource,
                    expires_at=refresh_expires,
                )
            )

            await session.commit()

        logger.info(
            "mcp_oauth_code_exchanged",
            client_id=client.client_id,
            user_email=row.user_email,
        )

        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL_HOURS * 3600,
            scope=" ".join(row.scopes) if row.scopes else None,
            refresh_token=refresh_token_str,
        )

    # ------------------------------------------------------------------
    # Refresh tokens
    # ------------------------------------------------------------------

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        async with self._session_maker() as session:
            result = await session.execute(
                select(MCPOAuthRefreshTokenDB).where(
                    MCPOAuthRefreshTokenDB.token == refresh_token
                )
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        if (
            row.expires_at
            and row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)
        ):
            return None

        return RefreshToken(
            token=row.token,
            client_id=row.client_id,
            scopes=row.scopes or [],
            expires_at=int(row.expires_at.replace(tzinfo=timezone.utc).timestamp())
            if row.expires_at
            else None,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        async with self._session_maker() as session:
            # Fetch the old refresh token row for user info
            result = await session.execute(
                select(MCPOAuthRefreshTokenDB).where(
                    MCPOAuthRefreshTokenDB.token == refresh_token.token
                )
            )
            old_row = result.scalar_one_or_none()
            if old_row is None:
                raise ValueError("Refresh token not found")

            # Delete old refresh token (rotation)
            await session.execute(
                delete(MCPOAuthRefreshTokenDB).where(
                    MCPOAuthRefreshTokenDB.token == refresh_token.token
                )
            )

            # Create new JWT
            now = datetime.now(timezone.utc)
            effective_scopes = scopes if scopes else (old_row.scopes or [])
            payload = {
                "sub": str(old_row.user_id) if old_row.user_id else None,
                "email": old_row.user_email,
                "client_id": client.client_id,
                "roles": old_row.user_roles or [],
                "permissions": old_row.user_permissions or [],
                "scopes": effective_scopes,
                "iss": "vizzhub",
                "aud": "vizzhub-mcp",
                "iat": now,
                "exp": now + timedelta(hours=ACCESS_TOKEN_TTL_HOURS),
            }
            new_access_token = jwt.encode(
                payload, self._jwt_secret, algorithm="HS256"
            )

            # Create new refresh token
            new_refresh_str = secrets.token_urlsafe(48)
            refresh_expires = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)

            session.add(
                MCPOAuthRefreshTokenDB(
                    token=new_refresh_str,
                    client_id=client.client_id,
                    user_id=old_row.user_id,
                    user_email=old_row.user_email,
                    user_roles=old_row.user_roles,
                    user_permissions=old_row.user_permissions,
                    scopes=effective_scopes,
                    resource=old_row.resource,
                    expires_at=refresh_expires,
                )
            )

            await session.commit()

        logger.info(
            "mcp_oauth_refresh_token_exchanged",
            client_id=client.client_id,
            user_email=old_row.user_email,
        )

        return OAuthToken(
            access_token=new_access_token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL_HOURS * 3600,
            scope=" ".join(effective_scopes) if effective_scopes else None,
            refresh_token=new_refresh_str,
        )

    # ------------------------------------------------------------------
    # Access token (JWT — no DB lookup needed)
    # ------------------------------------------------------------------

    async def load_access_token(self, token: str) -> AccessToken | None:
        try:
            payload = jwt.decode(
                token,
                self._jwt_secret,
                algorithms=["HS256"],
                audience="vizzhub-mcp",
                issuer="vizzhub",
            )
            return AccessToken(
                token=token,
                client_id=payload.get("client_id", "unknown"),
                scopes=payload.get("scopes", []),
                expires_at=payload.get("exp"),
            )
        except JWTError:
            return None

    # ------------------------------------------------------------------
    # Revocation
    # ------------------------------------------------------------------

    async def revoke_token(
        self, token: AccessToken | RefreshToken
    ) -> None:
        async with self._session_maker() as session:
            await session.execute(
                delete(MCPOAuthRefreshTokenDB).where(
                    MCPOAuthRefreshTokenDB.token == token.token
                )
            )
            await session.commit()
        logger.info("mcp_oauth_token_revoked", token_prefix=token.token[:8] + "...")
