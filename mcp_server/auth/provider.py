"""VizzHub OAuth provider — bridges MCP SDK auth to Google SSO."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

import structlog
from jose import jwt
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.models.mcp_oauth import (
    MCPOAuthClientDB,
    MCPOAuthCodeDB,
    MCPOAuthRefreshTokenDB,
)
from app.core.models.user import UserDB
from app.core.permissions.resolver import resolve_permissions
from mcp_server.auth.token_verifier import VizzHubTokenVerifier

logger = structlog.get_logger()

ACCESS_TOKEN_TTL_HOURS = 2
REFRESH_TOKEN_TTL_DAYS = 30
AUTH_CODE_TTL_MINUTES = 5

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_SCOPES = "openid email profile"

# Without a consent screen, the redirect_uri allowlist is what stops a rogue
# DCR client from harvesting codes: only known MCP hosts' callbacks and loopback
# (Claude Code / Desktop, Gemini CLI) may receive them. To support a new MCP
# client, add its documented callback here.
ALLOWED_REDIRECT_URIS = frozenset({
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
    "https://chatgpt.com/connector_platform_oauth_redirect",
})
# (host, path prefix) pairs whose final path segment is a per-connector id,
# e.g. ChatGPT's https://chatgpt.com/connector/oauth/{callback_id}.
ALLOWED_REDIRECT_ID_PREFIXES = frozenset({
    ("chatgpt.com", "/connector/oauth/"),
})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_CALLBACK_ID = re.compile(r"[A-Za-z0-9_-]+")


def is_allowed_redirect_uri(uri: str) -> bool:
    if uri in ALLOWED_REDIRECT_URIS:
        return True
    parts = urlsplit(uri)
    if parts.scheme == "http":
        return parts.hostname in LOOPBACK_HOSTS
    if parts.scheme != "https" or parts.port is not None or parts.query or parts.fragment:
        return False
    return any(
        parts.hostname == host
        and parts.path.startswith(prefix)
        and _CALLBACK_ID.fullmatch(parts.path.removeprefix(prefix)) is not None
        for host, prefix in ALLOWED_REDIRECT_ID_PREFIXES
    )


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
        try:
            client = OAuthClientInformationFull(**row.client_info)
        except ValidationError:
            logger.warning("mcp_oauth_client_invalid", client_id=client_id)
            return None
        # Clients registered before the allowlist existed are treated as unknown.
        if not all(is_allowed_redirect_uri(str(u)) for u in client.redirect_uris or []):
            logger.warning("mcp_oauth_client_redirect_rejected", client_id=client_id)
            return None
        return client

    async def register_client(
        self, client_info: OAuthClientInformationFull
    ) -> None:
        """Store a dynamically registered client.

        The SDK handler generates client_id/secret, passes them here, then
        returns its own copy to the caller — our return value is ignored.
        We must store the SAME client_id the SDK generated.
        """
        rejected = [
            str(u) for u in client_info.redirect_uris or []
            if not is_allowed_redirect_uri(str(u))
        ]
        if rejected:
            logger.warning(
                "mcp_oauth_client_registration_rejected",
                redirect_uris=rejected,
                client_name=client_info.client_name,
            )
            raise RegistrationError(
                error="invalid_redirect_uri",
                error_description="redirect_uri not allowed for this server",
            )

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
        if params.resource and params.resource.rstrip("/") != self._base_url:
            raise AuthorizeError(
                error="invalid_request",
                error_description="resource does not match this server",
            )

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

        # Pre-callback rows (code = state sent to Google) carry no user yet.
        if row is None or not row.user_email:
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
            # DELETE … RETURNING makes consumption atomic: of two concurrent
            # redemptions only one gets the row back.
            result = await session.execute(
                delete(MCPOAuthCodeDB)
                .where(
                    MCPOAuthCodeDB.code == authorization_code.code,
                    MCPOAuthCodeDB.client_id == client.client_id,
                )
                .returning(MCPOAuthCodeDB)
            )
            row = result.scalar_one_or_none()
            if row is None or not row.user_email or row.user_id is None:
                raise TokenError(
                    error="invalid_grant",
                    error_description="authorization code is invalid or already used",
                )

            fresh_roles, fresh_permissions = await self._resolve_active_user(
                session, row.user_id
            )
            effective_scopes = row.scopes or []
            access_token, _ = self._build_access_token(
                user_id=str(row.user_id),
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

    @staticmethod
    async def _resolve_active_user(
        session: AsyncSession, user_id: uuid.UUID,
    ) -> tuple[list[str], list[str]]:
        """Return fresh (roles, permissions), refusing deactivated or deleted users.

        On refusal the already-deleted grant is committed away: it is useless.
        """
        active = await session.scalar(select(UserDB.active).where(UserDB.id == user_id))
        if not active:
            await session.commit()
            logger.warning("mcp_oauth_grant_user_inactive", user_id=str(user_id))
            raise TokenError(
                error="invalid_grant",
                error_description="user is inactive",
            )
        return await resolve_permissions(session, str(user_id))

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
                delete(MCPOAuthRefreshTokenDB)
                .where(
                    MCPOAuthRefreshTokenDB.token == refresh_token.token,
                    MCPOAuthRefreshTokenDB.client_id == client.client_id,
                )
                .returning(MCPOAuthRefreshTokenDB)
            )
            old_row = result.scalar_one_or_none()
            # Legacy rows without user_id cannot be checked for deactivation;
            # force those clients through a fresh login instead.
            if old_row is None or old_row.user_id is None:
                raise TokenError(
                    error="invalid_grant",
                    error_description="refresh token is invalid or already used",
                )

            fresh_roles, fresh_permissions = await self._resolve_active_user(
                session, old_row.user_id
            )
            effective_scopes = scopes if scopes else (old_row.scopes or [])
            new_access_token, _ = self._build_access_token(
                user_id=str(old_row.user_id),
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
        """Delete the refresh token.

        Access tokens are stateless JWTs: revoking one is a no-op and it stays
        valid until expiry (ACCESS_TOKEN_TTL_HOURS).
        """
        async with self._session_maker() as session:
            await session.execute(
                delete(MCPOAuthRefreshTokenDB).where(
                    MCPOAuthRefreshTokenDB.token == token.token
                )
            )
            await session.commit()
        logger.info("mcp_oauth_token_revoked", token_prefix=token.token[:8] + "...")
