"""VizzHub OAuth provider — bridges MCP SDK auth to Google SSO."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import structlog
from jose import jwt
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
from app.core.permissions.resolver import resolve_permissions
from mcp_server.auth.token_verifier import VizzHubTokenVerifier

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
        self._token_verifier: VizzHubTokenVerifier | None = None

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _build_access_token(
        self,
        *,
        user_id: str | None,
        email: str | None,
        client_id: str,
        roles: list[str],
        permissions: list[str],
        scopes: list[str],
    ) -> tuple[str, datetime]:
        """Create a signed JWT access token. Returns (token_str, expiry)."""
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(hours=ACCESS_TOKEN_TTL_HOURS)
        payload = {
            "sub": user_id,
            "email": email,
            "client_id": client_id,
            "roles": roles,
            "permissions": permissions,
            "scopes": scopes,
            "iss": "vizzhub",
            "aud": "vizzhub-mcp",
            "iat": now,
            "exp": expiry,
        }
        return jwt.encode(payload, self._jwt_secret, algorithm="HS256"), expiry

    @staticmethod
    def _build_refresh_token_row(
        *,
        client_id: str,
        user_id,
        user_email: str | None,
        user_roles: list[str] | None,
        user_permissions: list[str] | None,
        scopes: list[str] | None,
        resource: str | None,
    ) -> tuple[str, MCPOAuthRefreshTokenDB]:
        """Create a new refresh token string and DB row. Returns (token_str, row)."""
        token_str = secrets.token_urlsafe(48)
        row = MCPOAuthRefreshTokenDB(
            token=token_str,
            client_id=client_id,
            user_id=user_id,
            user_email=user_email,
            user_roles=user_roles,
            user_permissions=user_permissions,
            scopes=scopes,
            resource=resource,
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
        )
        return token_str, row

    @staticmethod
    def _build_oauth_token(
        access_token: str,
        refresh_token: str,
        scopes: list[str] | None,
    ) -> OAuthToken:
        """Build the OAuthToken response."""
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL_HOURS * 3600,
            scope=" ".join(scopes) if scopes else None,
            refresh_token=refresh_token,
        )

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
    ) -> None:
        """Store a dynamically registered client.

        The SDK handler generates client_id/secret, passes them here, then
        returns its own copy to the caller — our return value is ignored.
        We must store the SAME client_id the SDK generated.
        """
        async with self._session_maker() as session:
            session.add(
                MCPOAuthClientDB(
                    client_id=client_info.client_id,
                    client_secret=client_info.client_secret,
                    client_info=client_info.model_dump(mode="json"),
                )
            )
            await session.commit()

        logger.info("mcp_oauth_client_registered", client_id=client_info.client_id)

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
                    mcp_state=params.state,
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
                select(MCPOAuthCodeDB).where(
                    MCPOAuthCodeDB.code == authorization_code,
                    MCPOAuthCodeDB.client_id == client.client_id,
                )
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
        async with self._session_maker() as session:
            result = await session.execute(
                select(MCPOAuthCodeDB).where(
                    MCPOAuthCodeDB.code == authorization_code.code
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise ValueError("Authorization code not found")

            if not row.user_email:
                raise ValueError("Authorization code has no associated user — callback incomplete")

            await session.execute(
                delete(MCPOAuthCodeDB).where(
                    MCPOAuthCodeDB.code == authorization_code.code
                )
            )

            effective_scopes = row.scopes or []
            if row.user_id:
                fresh_roles, fresh_permissions = await resolve_permissions(
                    session, str(row.user_id)
                )
            else:
                fresh_roles, fresh_permissions = (row.user_roles or []), (
                    row.user_permissions or []
                )
            access_token, _ = self._build_access_token(
                user_id=str(row.user_id) if row.user_id else None,
                email=row.user_email,
                client_id=client.client_id,
                roles=fresh_roles,
                permissions=fresh_permissions,
                scopes=effective_scopes,
            )

            refresh_token_str, refresh_row = self._build_refresh_token_row(
                client_id=client.client_id,
                user_id=row.user_id,
                user_email=row.user_email,
                user_roles=fresh_roles,
                user_permissions=fresh_permissions,
                scopes=row.scopes,
                resource=row.resource,
            )
            session.add(refresh_row)
            await session.commit()

        logger.info(
            "mcp_oauth_code_exchanged",
            client_id=client.client_id,
            user_email=row.user_email,
        )

        return self._build_oauth_token(access_token, refresh_token_str, effective_scopes)

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
                    MCPOAuthRefreshTokenDB.token == refresh_token,
                    MCPOAuthRefreshTokenDB.client_id == client.client_id,
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
            result = await session.execute(
                select(MCPOAuthRefreshTokenDB).where(
                    MCPOAuthRefreshTokenDB.token == refresh_token.token
                )
            )
            old_row = result.scalar_one_or_none()
            if old_row is None:
                raise ValueError("Refresh token not found")

            await session.execute(
                delete(MCPOAuthRefreshTokenDB).where(
                    MCPOAuthRefreshTokenDB.token == refresh_token.token
                )
            )

            effective_scopes = scopes if scopes else (old_row.scopes or [])
            if old_row.user_id:
                fresh_roles, fresh_permissions = await resolve_permissions(
                    session, str(old_row.user_id)
                )
            else:
                fresh_roles, fresh_permissions = (old_row.user_roles or []), (
                    old_row.user_permissions or []
                )
            new_access_token, _ = self._build_access_token(
                user_id=str(old_row.user_id) if old_row.user_id else None,
                email=old_row.user_email,
                client_id=client.client_id,
                roles=fresh_roles,
                permissions=fresh_permissions,
                scopes=effective_scopes,
            )

            new_refresh_str, refresh_row = self._build_refresh_token_row(
                client_id=client.client_id,
                user_id=old_row.user_id,
                user_email=old_row.user_email,
                user_roles=fresh_roles,
                user_permissions=fresh_permissions,
                scopes=effective_scopes,
                resource=old_row.resource,
            )
            session.add(refresh_row)
            await session.commit()

        logger.info(
            "mcp_oauth_refresh_token_exchanged",
            client_id=client.client_id,
            user_email=old_row.user_email,
        )

        return self._build_oauth_token(new_access_token, new_refresh_str, effective_scopes)

    # ------------------------------------------------------------------
    # Access token (JWT — no DB lookup needed)
    # ------------------------------------------------------------------

    async def load_access_token(self, token: str) -> AccessToken | None:
        if self._token_verifier is None:
            self._token_verifier = VizzHubTokenVerifier(secret_key=self._jwt_secret)
        return await self._token_verifier.verify_token(token)

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
