"""JWT token verification for the VizzHub MCP server."""

from __future__ import annotations

import asyncio

from jose import JWTError, jwt
from mcp.server.auth.provider import AccessToken


class VizzHubTokenVerifier:
    """Verify MCP access tokens (JWTs signed with the backend's shared secret).

    Implements the MCP SDK ``TokenVerifier`` protocol so it can be plugged
    directly into the SDK's bearer-auth middleware.
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
            return AccessToken(
                token=token,
                client_id=payload.get("client_id", "unknown"),
                scopes=payload.get("scopes", []),
                expires_at=payload.get("exp"),
            )
        except JWTError:
            return None
