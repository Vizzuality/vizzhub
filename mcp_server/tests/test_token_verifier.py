"""Unit tests for VizzHubTokenVerifier — JWT validation for MCP tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from mcp_server.auth.token_verifier import VizzHubTokenVerifier

SECRET = "test-secret-key-for-mcp-verifier"
WRONG_SECRET = "completely-wrong-secret"
ALGORITHM = "HS256"


def _make_token(
    claims: dict | None = None,
    secret: str = SECRET,
    algorithm: str = ALGORITHM,
) -> str:
    """Helper to mint a JWT for testing."""
    payload = {
        "sub": "user-123",
        "client_id": "mcp-client",
        "scopes": ["read", "write"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, secret, algorithm=algorithm)


@pytest.fixture
def verifier() -> VizzHubTokenVerifier:
    return VizzHubTokenVerifier(secret_key=SECRET, algorithm=ALGORITHM)


@pytest.mark.asyncio
async def test_verify_valid_token(verifier: VizzHubTokenVerifier) -> None:
    token = _make_token()
    result = await verifier.verify_token(token)

    assert result is not None
    assert result.token == token
    assert result.client_id == "mcp-client"
    assert result.scopes == ["read", "write"]
    assert result.expires_at is not None


@pytest.mark.asyncio
async def test_verify_expired_token(verifier: VizzHubTokenVerifier) -> None:
    token = _make_token(claims={
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    })
    result = await verifier.verify_token(token)

    assert result is None


@pytest.mark.asyncio
async def test_verify_invalid_signature(verifier: VizzHubTokenVerifier) -> None:
    token = _make_token(secret=WRONG_SECRET)
    result = await verifier.verify_token(token)

    assert result is None


@pytest.mark.asyncio
async def test_verify_malformed_token(verifier: VizzHubTokenVerifier) -> None:
    result = await verifier.verify_token("not.a.valid.jwt.at.all")

    assert result is None


@pytest.mark.asyncio
async def test_verify_empty_token(verifier: VizzHubTokenVerifier) -> None:
    result = await verifier.verify_token("")

    assert result is None


@pytest.mark.asyncio
async def test_verify_missing_claims_uses_defaults(
    verifier: VizzHubTokenVerifier,
) -> None:
    """A JWT without client_id/scopes still decodes — defaults are applied."""
    token = jwt.encode(
        {"sub": "user-456", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        SECRET,
        algorithm=ALGORITHM,
    )
    result = await verifier.verify_token(token)

    assert result is not None
    assert result.client_id == "unknown"
    assert result.scopes == []


@pytest.mark.asyncio
async def test_verify_token_preserves_raw_token(
    verifier: VizzHubTokenVerifier,
) -> None:
    """The AccessToken.token field must be the original raw JWT string."""
    token = _make_token()
    result = await verifier.verify_token(token)

    assert result is not None
    assert result.token == token


@pytest.mark.asyncio
async def test_verify_token_with_no_expiry(
    verifier: VizzHubTokenVerifier,
) -> None:
    """A JWT without an exp claim should still verify (jose allows it by default)."""
    token = jwt.encode(
        {"sub": "user-789", "client_id": "no-exp"},
        SECRET,
        algorithm=ALGORITHM,
    )
    result = await verifier.verify_token(token)

    assert result is not None
    assert result.client_id == "no-exp"
    assert result.expires_at is None
