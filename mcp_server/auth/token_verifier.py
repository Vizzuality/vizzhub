"""JWT token verification for the VizzHub MCP server."""

from __future__ import annotations

from jose import JWTError, jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier  # noqa: F401 — TokenVerifier used for protocol compliance


class VizzHubTokenVerifier:
    """Verify MCP access tokens (JWTs signed with the backend's shared secret).

    Implements the MCP SDK ``TokenVerifier`` protocol so it can be plugged
    directly into the SDK's bearer-auth middleware.
    """

    def __init__(self, secret_key: str, algorithm: str = "HS256") -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm

    async def verify_token(self, token: str) -> AccessToken | None:
        """Decode and validate *token*, returning an ``AccessToken`` on success."""
        try:
            payload = jwt.decode(
                token, self._secret_key, algorithms=[self._algorithm],
            )
            return AccessToken(
                token=token,
                client_id=payload.get("client_id", "unknown"),
                scopes=payload.get("scopes", []),
                expires_at=payload.get("exp"),
            )
        except JWTError:
            return None
