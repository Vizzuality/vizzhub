"""Tests for VizzHubOAuthProvider — OAuth adapter for MCP SDK."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from jose import jwt
from mcp.shared.auth import OAuthClientInformationFull
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.models.mcp_oauth import (
    MCPOAuthClientDB,
    MCPOAuthCodeDB,
    MCPOAuthRefreshTokenDB,
)
from app.core.models.user import UserDB
from app.database import Base
from mcp_server.auth.provider import (
    ACCESS_TOKEN_TTL_HOURS,
    AUTH_CODE_TTL_MINUTES,
    VizzHubOAuthProvider,
)
from mcp_server.tests.conftest import TEST_DATABASE_URL

JWT_SECRET = "test-jwt-secret-for-provider"
GOOGLE_CLIENT_ID = "test-google-client-id.apps.googleusercontent.com"
ALLOWED_DOMAIN = "vizzuality.com"
BASE_URL = "https://hub.vizzuality.com/mcp"

TEST_CLIENT_ID = "test-mcp-client"
TEST_CLIENT_SECRET = "test-mcp-secret"


def _client_info_dict() -> dict:
    return {
        "client_id": TEST_CLIENT_ID,
        "client_secret": TEST_CLIENT_SECRET,
        "redirect_uris": ["http://localhost:3000/callback"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "client_name": "Test MCP Client",
        "token_endpoint_auth_method": "client_secret_post",
    }


@pytest_asyncio.fixture
async def session_maker():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield maker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def provider(session_maker) -> VizzHubOAuthProvider:
    return VizzHubOAuthProvider(
        session_maker=session_maker,
        jwt_secret=JWT_SECRET,
        google_client_id=GOOGLE_CLIENT_ID,
        allowed_google_domain=ALLOWED_DOMAIN,
        base_url=BASE_URL,
    )


@pytest_asyncio.fixture
async def test_user_id(session_maker) -> uuid.UUID:
    """Create a user row in the DB for FK references."""
    user_id = uuid.uuid4()
    async with session_maker() as session:
        session.add(
            UserDB(id=user_id, email="test@vizzuality.com", name="Test User")
        )
        await session.commit()
    return user_id


@pytest_asyncio.fixture
async def registered_client(session_maker) -> OAuthClientInformationFull:
    """Insert a pre-registered client into the DB."""
    info = _client_info_dict()
    client_full = OAuthClientInformationFull(**info)
    async with session_maker() as session:
        session.add(
            MCPOAuthClientDB(
                client_id=TEST_CLIENT_ID,
                client_secret=TEST_CLIENT_SECRET,
                client_info=client_full.model_dump(mode="json"),
            )
        )
        await session.commit()
    return client_full


# ------------------------------------------------------------------
# Client registration
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_client_creates_db_row(
    provider: VizzHubOAuthProvider,
    session_maker,
) -> None:
    client_info = OAuthClientInformationFull(
        redirect_uris=["http://localhost:3000/callback"],
        client_name="Dynamic Client",
    )
    result = provider.register_client(client_info)
    result = await result

    assert result.client_id is not None
    assert result.client_secret is not None

    async with session_maker() as session:
        row = await session.execute(
            select(MCPOAuthClientDB).where(
                MCPOAuthClientDB.client_id == result.client_id
            )
        )
        db_row = row.scalar_one_or_none()
    assert db_row is not None
    assert db_row.client_info["client_id"] == result.client_id


@pytest.mark.asyncio
async def test_get_client_returns_registered_client(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
) -> None:
    result = await provider.get_client(TEST_CLIENT_ID)

    assert result is not None
    assert result.client_id == TEST_CLIENT_ID
    assert result.client_name == "Test MCP Client"


@pytest.mark.asyncio
async def test_get_client_returns_none_for_unknown(
    provider: VizzHubOAuthProvider,
) -> None:
    result = await provider.get_client("nonexistent-client-id")
    assert result is None


# ------------------------------------------------------------------
# Authorize
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_authorize_returns_google_url(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
) -> None:
    from mcp.server.auth.provider import AuthorizationParams

    params = AuthorizationParams(
        state="test-state",
        scopes=["read"],
        code_challenge="test-challenge-abc123",
        redirect_uri="http://localhost:3000/callback",
        redirect_uri_provided_explicitly=True,
    )
    url = await provider.authorize(registered_client, params)

    assert "accounts.google.com" in url
    assert GOOGLE_CLIENT_ID in url
    assert "state=" in url
    assert "response_type=code" in url


@pytest.mark.asyncio
async def test_authorize_stores_state_in_db(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    session_maker,
) -> None:
    from mcp.server.auth.provider import AuthorizationParams

    params = AuthorizationParams(
        state="test-state",
        scopes=["read", "write"],
        code_challenge="test-challenge-xyz",
        redirect_uri="http://localhost:3000/callback",
        redirect_uri_provided_explicitly=True,
        resource="https://hub.vizzuality.com/mcp",
    )
    url = await provider.authorize(registered_client, params)

    # Extract state (= code) from URL
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    state_code = parse_qs(parsed.query)["state"][0]

    async with session_maker() as session:
        result = await session.execute(
            select(MCPOAuthCodeDB).where(MCPOAuthCodeDB.code == state_code)
        )
        row = result.scalar_one_or_none()

    assert row is not None
    assert row.client_id == TEST_CLIENT_ID
    assert row.code_challenge == "test-challenge-xyz"
    assert row.scopes == ["read", "write"]
    assert row.redirect_uri_provided_explicitly is True
    assert row.resource == "https://hub.vizzuality.com/mcp"
    assert row.mcp_state == "test-state"
    assert row.user_id is None


# ------------------------------------------------------------------
# Load authorization code
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_authorization_code_valid(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    session_maker,
) -> None:
    code = "valid-test-code-12345"
    async with session_maker() as session:
        session.add(
            MCPOAuthCodeDB(
                code=code,
                client_id=TEST_CLIENT_ID,
                code_challenge="challenge123",
                redirect_uri="http://localhost:3000/callback",
                redirect_uri_provided_explicitly=True,
                scopes=["read"],
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        await session.commit()

    result = await provider.load_authorization_code(registered_client, code)

    assert result is not None
    assert result.code == code
    assert result.client_id == TEST_CLIENT_ID
    assert result.code_challenge == "challenge123"
    assert result.scopes == ["read"]


@pytest.mark.asyncio
async def test_load_authorization_code_expired(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    session_maker,
) -> None:
    code = "expired-test-code-999"
    async with session_maker() as session:
        session.add(
            MCPOAuthCodeDB(
                code=code,
                client_id=TEST_CLIENT_ID,
                code_challenge="challenge456",
                redirect_uri="http://localhost:3000/callback",
                redirect_uri_provided_explicitly=True,
                scopes=["read"],
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()

    result = await provider.load_authorization_code(registered_client, code)
    assert result is None


# ------------------------------------------------------------------
# Exchange authorization code
# ------------------------------------------------------------------


@pytest_asyncio.fixture
async def code_row_with_user(
    session_maker, registered_client, test_user_id
) -> MCPOAuthCodeDB:
    """Insert a code row with user info (simulating what the callback does)."""
    code = "exchange-test-code-abc"

    async with session_maker() as session:
        row = MCPOAuthCodeDB(
            code=code,
            client_id=TEST_CLIENT_ID,
            code_challenge="challenge-for-exchange",
            redirect_uri="http://localhost:3000/callback",
            redirect_uri_provided_explicitly=True,
            scopes=["read"],
            user_id=test_user_id,
            user_email="test@vizzuality.com",
            user_roles=["user", "manager"],
            user_permissions=["read:iso", "write:iso"],
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)

    return row


@pytest.mark.asyncio
async def test_exchange_authorization_code_returns_tokens(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    code_row_with_user: MCPOAuthCodeDB,
) -> None:
    from mcp.server.auth.provider import AuthorizationCode

    auth_code = AuthorizationCode(
        code=code_row_with_user.code,
        client_id=TEST_CLIENT_ID,
        code_challenge="challenge-for-exchange",
        redirect_uri="http://localhost:3000/callback",
        redirect_uri_provided_explicitly=True,
        scopes=["read"],
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp(),
    )

    token = await provider.exchange_authorization_code(registered_client, auth_code)

    assert token.access_token is not None
    assert token.refresh_token is not None
    assert token.token_type == "Bearer"
    assert token.expires_in == ACCESS_TOKEN_TTL_HOURS * 3600

    # Verify the JWT payload
    payload = jwt.decode(
        token.access_token,
        JWT_SECRET,
        algorithms=["HS256"],
        audience="vizzhub-mcp",
        issuer="vizzhub",
    )
    assert payload["sub"] == str(code_row_with_user.user_id)
    assert payload["email"] == "test@vizzuality.com"
    assert payload["roles"] == ["user", "manager"]
    assert payload["permissions"] == ["read:iso", "write:iso"]
    assert payload["scopes"] == ["read"]
    assert payload["iss"] == "vizzhub"
    assert payload["aud"] == "vizzhub-mcp"


@pytest.mark.asyncio
async def test_exchange_authorization_code_deletes_code(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    code_row_with_user: MCPOAuthCodeDB,
    session_maker,
) -> None:
    from mcp.server.auth.provider import AuthorizationCode

    auth_code = AuthorizationCode(
        code=code_row_with_user.code,
        client_id=TEST_CLIENT_ID,
        code_challenge="challenge-for-exchange",
        redirect_uri="http://localhost:3000/callback",
        redirect_uri_provided_explicitly=True,
        scopes=["read"],
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp(),
    )

    await provider.exchange_authorization_code(registered_client, auth_code)

    async with session_maker() as session:
        result = await session.execute(
            select(MCPOAuthCodeDB).where(
                MCPOAuthCodeDB.code == code_row_with_user.code
            )
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_load_authorization_code_preserves_challenge(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    session_maker,
    test_user_id,
) -> None:
    """PKCE verification is done by the SDK caller, not our provider directly.

    Our provider stores the code_challenge and the SDK validates it
    before calling exchange_authorization_code.  This test verifies
    the code row is correctly stored and can be loaded with its challenge.
    """
    code = "pkce-test-code"
    async with session_maker() as session:
        session.add(
            MCPOAuthCodeDB(
                code=code,
                client_id=TEST_CLIENT_ID,
                code_challenge="expected-challenge-value",
                redirect_uri="http://localhost:3000/callback",
                redirect_uri_provided_explicitly=True,
                scopes=["read"],
                user_email="pkce@vizzuality.com",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        await session.commit()

    auth_code = await provider.load_authorization_code(registered_client, code)
    assert auth_code is not None
    assert auth_code.code_challenge == "expected-challenge-value"


@pytest.mark.asyncio
async def test_exchange_authorization_code_null_user_raises(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    session_maker,
) -> None:
    """exchange_authorization_code raises ValueError when callback never populated user info."""
    from mcp.server.auth.provider import AuthorizationCode

    code = "null-user-code-abc"
    async with session_maker() as session:
        session.add(
            MCPOAuthCodeDB(
                code=code,
                client_id=TEST_CLIENT_ID,
                code_challenge="some-challenge",
                redirect_uri="http://localhost:3000/callback",
                redirect_uri_provided_explicitly=True,
                scopes=["read"],
                user_id=None,
                user_email=None,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        await session.commit()

    auth_code = AuthorizationCode(
        code=code,
        client_id=TEST_CLIENT_ID,
        code_challenge="some-challenge",
        redirect_uri="http://localhost:3000/callback",
        redirect_uri_provided_explicitly=True,
        scopes=["read"],
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp(),
    )

    with pytest.raises(ValueError, match="callback incomplete"):
        await provider.exchange_authorization_code(registered_client, auth_code)


# ------------------------------------------------------------------
# Refresh tokens
# ------------------------------------------------------------------


@pytest_asyncio.fixture
async def refresh_token_row(
    session_maker, registered_client, test_user_id
) -> MCPOAuthRefreshTokenDB:
    """Insert a refresh token row in the DB."""
    async with session_maker() as session:
        row = MCPOAuthRefreshTokenDB(
            token="test-refresh-token-abc",
            client_id=TEST_CLIENT_ID,
            user_id=test_user_id,
            user_email="refresh@vizzuality.com",
            user_roles=["user"],
            user_permissions=["read:iso"],
            scopes=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)

    return row


@pytest.mark.asyncio
async def test_load_refresh_token_valid(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    refresh_token_row: MCPOAuthRefreshTokenDB,
) -> None:
    result = await provider.load_refresh_token(
        registered_client, refresh_token_row.token
    )

    assert result is not None
    assert result.token == "test-refresh-token-abc"
    assert result.client_id == TEST_CLIENT_ID
    assert result.scopes == ["read"]


@pytest.mark.asyncio
async def test_load_refresh_token_expired(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    session_maker,
) -> None:
    async with session_maker() as session:
        session.add(
            MCPOAuthRefreshTokenDB(
                token="expired-refresh-token",
                client_id=TEST_CLIENT_ID,
                scopes=["read"],
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        )
        await session.commit()

    result = await provider.load_refresh_token(
        registered_client, "expired-refresh-token"
    )
    assert result is None


@pytest.mark.asyncio
async def test_exchange_refresh_token_rotates_tokens(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    refresh_token_row: MCPOAuthRefreshTokenDB,
    session_maker,
) -> None:
    from mcp.server.auth.provider import RefreshToken

    old_refresh = RefreshToken(
        token=refresh_token_row.token,
        client_id=TEST_CLIENT_ID,
        scopes=["read"],
    )

    token = await provider.exchange_refresh_token(
        registered_client, old_refresh, scopes=["read"]
    )

    assert token.access_token is not None
    assert token.refresh_token is not None
    assert token.refresh_token != refresh_token_row.token

    # Old token should be gone
    async with session_maker() as session:
        result = await session.execute(
            select(MCPOAuthRefreshTokenDB).where(
                MCPOAuthRefreshTokenDB.token == refresh_token_row.token
            )
        )
        assert result.scalar_one_or_none() is None

    # New token should exist
    async with session_maker() as session:
        result = await session.execute(
            select(MCPOAuthRefreshTokenDB).where(
                MCPOAuthRefreshTokenDB.token == token.refresh_token
            )
        )
        new_row = result.scalar_one_or_none()
        assert new_row is not None
        assert new_row.user_email == "refresh@vizzuality.com"


# ------------------------------------------------------------------
# Access token (JWT)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_access_token_valid_jwt(
    provider: VizzHubOAuthProvider,
) -> None:
    now = datetime.now(timezone.utc)
    token_str = jwt.encode(
        {
            "sub": "user-123",
            "client_id": "my-client",
            "scopes": ["read", "write"],
            "iss": "vizzhub",
            "aud": "vizzhub-mcp",
            "exp": now + timedelta(hours=2),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    result = await provider.load_access_token(token_str)

    assert result is not None
    assert result.token == token_str
    assert result.client_id == "my-client"
    assert result.scopes == ["read", "write"]


@pytest.mark.asyncio
async def test_load_access_token_invalid_jwt(
    provider: VizzHubOAuthProvider,
) -> None:
    result = await provider.load_access_token("garbage.not.a.jwt")
    assert result is None


@pytest.mark.asyncio
async def test_load_access_token_wrong_issuer(
    provider: VizzHubOAuthProvider,
) -> None:
    token_str = jwt.encode(
        {
            "sub": "user-123",
            "iss": "wrong-issuer",
            "aud": "vizzhub-mcp",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    result = await provider.load_access_token(token_str)
    assert result is None


# ------------------------------------------------------------------
# Revocation
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revoke_token_deletes_refresh_token(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    refresh_token_row: MCPOAuthRefreshTokenDB,
    session_maker,
) -> None:
    from mcp.server.auth.provider import RefreshToken

    rt = RefreshToken(
        token=refresh_token_row.token,
        client_id=TEST_CLIENT_ID,
        scopes=["read"],
    )

    await provider.revoke_token(rt)

    async with session_maker() as session:
        result = await session.execute(
            select(MCPOAuthRefreshTokenDB).where(
                MCPOAuthRefreshTokenDB.token == refresh_token_row.token
            )
        )
        assert result.scalar_one_or_none() is None
