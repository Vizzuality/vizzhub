"""Unit tests for VizzHubTokenVerifier — JWT validation for MCP tokens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from mcp_server.auth.token_verifier import VizzHubTokenVerifier

TEST_SECRET = "test-secret-key-for-mcp-verifier"
WRONG_SECRET = "completely-wrong-secret"
ALGORITHM = "HS256"


def _make_token(claims: dict | None = None, secret: str = TEST_SECRET) -> str:
    """Helper to mint a JWT for testing."""
    base = {
        "client_id": "test-user",
        "scopes": ["read"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iss": "vizzhub",
        "aud": "vizzhub-mcp",
    }
    if claims:
        base.update(claims)
    return jwt.encode(base, secret, algorithm="HS256")


@pytest.fixture
def verifier() -> VizzHubTokenVerifier:
    return VizzHubTokenVerifier(secret_key=TEST_SECRET, algorithm=ALGORITHM)


@pytest.mark.asyncio
async def test_verify_valid_token(verifier: VizzHubTokenVerifier) -> None:
    token = _make_token()
    result = await verifier.verify_token(token)

    assert result is not None
    assert result.token == token
    assert result.client_id == "test-user"
    assert result.scopes == ["read"]
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
        {
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iss": "vizzhub",
            "aud": "vizzhub-mcp",
        },
        TEST_SECRET,
        algorithm=ALGORITHM,
    )
    result = await verifier.verify_token(token)

    assert result is not None
    assert result.client_id == "unknown"
    assert result.scopes == []


@pytest.mark.asyncio
async def test_verify_token_with_no_expiry(
    verifier: VizzHubTokenVerifier,
) -> None:
    """A JWT without an exp claim should still verify (jose allows it by default)."""
    token = jwt.encode(
        {"client_id": "no-exp", "iss": "vizzhub", "aud": "vizzhub-mcp"},
        TEST_SECRET,
        algorithm=ALGORITHM,
    )
    result = await verifier.verify_token(token)

    assert result is not None
    assert result.client_id == "no-exp"
    assert result.expires_at is None


@pytest.mark.asyncio
async def test_verify_wrong_audience(verifier: VizzHubTokenVerifier) -> None:
    """A token with a different audience claim must be rejected."""
    token = _make_token(claims={"aud": "some-other-service"})
    result = await verifier.verify_token(token)

    assert result is None


@pytest.mark.asyncio
async def test_verify_wrong_issuer(verifier: VizzHubTokenVerifier) -> None:
    """A token issued by a different issuer must be rejected."""
    token = _make_token(claims={"iss": "some-other-issuer"})
    result = await verifier.verify_token(token)

    assert result is None


@pytest.mark.asyncio
async def test_verify_wrong_algorithm(verifier: VizzHubTokenVerifier) -> None:
    """A token signed with RS256 (or any non-HS256 algorithm) must be rejected."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    token = jwt.encode(
        {
            "client_id": "rs256-client",
            "iss": "vizzhub",
            "aud": "vizzhub-mcp",
        },
        private_key,
        algorithm="RS256",
    )
    result = await verifier.verify_token(token)

    assert result is None
