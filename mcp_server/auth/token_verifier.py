"""JWT token verification for the VizzHub MCP server."""

from __future__ import annotations

import asyncio

from jose import JWTError, jwt
from mcp.server.auth.provider import AccessToken

from mcp_server.data.base import McpUserContext, set_mcp_user


class VizzHubTokenVerifier:
    """Verify MCP access tokens (JWTs signed with the backend's shared secret).

    On success, also sets the McpUserContext ContextVar so that downstream
    tools and data functions can access user identity and permissions.
    """

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        audience: str = "vizzhub-mcp",
        issuer: str = "vizzhub",
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._audience = audience
        self._issuer = issuer

    async def verify_token(self, token: str) -> AccessToken | None:
        """Decode and validate *token*, returning an ``AccessToken`` on success."""
        try:
            payload = await asyncio.to_thread(
                jwt.decode, token, self._secret_key,
                algorithms=[self._algorithm],
                audience=self._audience, issuer=self._issuer,
            )
            set_mcp_user(McpUserContext(
                user_id=payload.get("sub", "unknown"),
                email=payload.get("email", ""),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
            ))
            return AccessToken(
                token=token,
                client_id=payload.get("client_id", "unknown"),
                scopes=payload.get("scopes", []),
                expires_at=payload.get("exp"),
            )
        except JWTError:
            return None
