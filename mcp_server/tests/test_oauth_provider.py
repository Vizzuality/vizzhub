"""Tests for VizzHubOAuthProvider — OAuth adapter for MCP SDK."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from jose import jwt
from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.models.mcp_oauth import (
    MCPOAuthClientDB,
    MCPOAuthCodeDB,
    MCPOAuthRefreshTokenDB,
)
from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import UserDB
from app.core.permissions.actions import Action
from app.database import Base
from mcp_server.auth.provider import (
    ACCESS_TOKEN_TTL_HOURS,
    AUTH_CODE_TTL_MINUTES,
    VizzHubOAuthProvider,
    is_allowed_redirect_uri,
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


async def _assign_role(
    session_maker: async_sessionmaker, user_id: uuid.UUID, role_name: str
) -> None:
    async with session_maker() as session:
        role = RoleDB(id=uuid.uuid4(), name=role_name)
        session.add(role)
        await session.flush()
        session.add(UserRoleDB(user_id=user_id, role_id=role.id))
        await session.commit()


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
        client_id="sdk-generated-uuid",
        client_secret="sdk-generated-secret",
        redirect_uris=["http://localhost:3000/callback"],
        client_name="Dynamic Client",
    )
    await provider.register_client(client_info)

    async with session_maker() as session:
        row = await session.execute(
            select(MCPOAuthClientDB).where(
                MCPOAuthClientDB.client_id == "sdk-generated-uuid"
            )
        )
        db_row = row.scalar_one_or_none()
    assert db_row is not None
    assert db_row.client_secret == "sdk-generated-secret"
    assert db_row.client_info["client_id"] == "sdk-generated-uuid"


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
                user_email="test@vizzuality.com",
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
    session_maker,
) -> None:
    from mcp.server.auth.provider import AuthorizationCode

    await _assign_role(session_maker, code_row_with_user.user_id, "user")

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

    payload = jwt.decode(
        token.access_token,
        JWT_SECRET,
        algorithms=["HS256"],
        audience="vizzhub-mcp",
        issuer="vizzhub",
    )
    assert payload["sub"] == str(code_row_with_user.user_id)
    assert payload["email"] == "test@vizzuality.com"
    assert payload["roles"] == ["user"]
    assert Action.DEVSTACK_VIEW in payload["permissions"]
    assert payload["scopes"] == ["read"]
    assert payload["iss"] == "vizzhub"
    assert payload["aud"] == "vizzhub-mcp"


@pytest.mark.asyncio
async def test_exchange_authorization_code_refreshes_stale_permissions(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    code_row_with_user: MCPOAuthCodeDB,
    session_maker,
) -> None:
    """The code row carries a stale permission snapshot (pre role update).
    The exchange must re-resolve from the DB and mint a JWT with the
    current role permissions, not the stored snapshot.
    """
    from mcp.server.auth.provider import AuthorizationCode

    await _assign_role(session_maker, code_row_with_user.user_id, "user")

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

    payload = jwt.decode(
        token.access_token,
        JWT_SECRET,
        algorithms=["HS256"],
        audience="vizzhub-mcp",
        issuer="vizzhub",
    )
    assert "read:iso" not in payload["permissions"]
    assert "write:iso" not in payload["permissions"]
    assert payload["roles"] == ["user"]
    assert Action.DEVSTACK_VIEW in payload["permissions"]

    async with session_maker() as session:
        new_refresh = await session.execute(
            select(MCPOAuthRefreshTokenDB).where(
                MCPOAuthRefreshTokenDB.token == token.refresh_token
            )
        )
        new_refresh_row = new_refresh.scalar_one()
        assert new_refresh_row.user_roles == ["user"]
        assert Action.DEVSTACK_VIEW in (new_refresh_row.user_permissions or [])


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
async def test_exchange_authorization_code_missing_code_raises(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
) -> None:
    """exchange_authorization_code raises invalid_grant when code not found in DB."""
    from mcp.server.auth.provider import AuthorizationCode

    auth_code = AuthorizationCode(
        code="nonexistent-code-xyz",
        client_id=TEST_CLIENT_ID,
        code_challenge="some-challenge",
        redirect_uri="http://localhost:3000/callback",
        redirect_uri_provided_explicitly=True,
        scopes=["read"],
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp(),
    )

    with pytest.raises(TokenError) as exc_info:
        await provider.exchange_authorization_code(registered_client, auth_code)
    assert exc_info.value.error == "invalid_grant"


@pytest.mark.asyncio
async def test_exchange_authorization_code_null_user_raises(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    session_maker,
) -> None:
    """A pre-callback row (no user yet) is neither loadable nor redeemable."""
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

    assert await provider.load_authorization_code(registered_client, code) is None
    with pytest.raises(TokenError) as exc_info:
        await provider.exchange_authorization_code(registered_client, auth_code)
    assert exc_info.value.error == "invalid_grant"


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

    await _assign_role(session_maker, refresh_token_row.user_id, "user")

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

    async with session_maker() as session:
        result = await session.execute(
            select(MCPOAuthRefreshTokenDB).where(
                MCPOAuthRefreshTokenDB.token == refresh_token_row.token
            )
        )
        assert result.scalar_one_or_none() is None

    async with session_maker() as session:
        result = await session.execute(
            select(MCPOAuthRefreshTokenDB).where(
                MCPOAuthRefreshTokenDB.token == token.refresh_token
            )
        )
        new_row = result.scalar_one_or_none()
        assert new_row is not None
        assert new_row.user_email == "refresh@vizzuality.com"
        assert new_row.user_roles == ["user"]
        assert Action.DEVSTACK_VIEW in (new_row.user_permissions or [])


@pytest.mark.asyncio
async def test_exchange_refresh_token_refreshes_stale_permissions(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    refresh_token_row: MCPOAuthRefreshTokenDB,
    session_maker,
) -> None:
    """A refresh token stored with an old permission snapshot must mint a
    new access token with the current permissions after the user's role
    gains a new permission.
    """
    from mcp.server.auth.provider import RefreshToken

    await _assign_role(session_maker, refresh_token_row.user_id, "user")

    old_refresh = RefreshToken(
        token=refresh_token_row.token,
        client_id=TEST_CLIENT_ID,
        scopes=["read"],
    )

    token = await provider.exchange_refresh_token(
        registered_client, old_refresh, scopes=["read"]
    )

    payload = jwt.decode(
        token.access_token,
        JWT_SECRET,
        algorithms=["HS256"],
        audience="vizzhub-mcp",
        issuer="vizzhub",
    )
    assert payload["roles"] == ["user"]
    assert Action.DEVSTACK_VIEW in payload["permissions"]


@pytest.mark.asyncio
async def test_exchange_refresh_token_missing_token_raises(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
) -> None:
    """exchange_refresh_token raises invalid_grant when token not found in DB."""
    from mcp.server.auth.provider import RefreshToken

    fake_token = RefreshToken(
        token="nonexistent-refresh-token-xyz",
        client_id=TEST_CLIENT_ID,
        scopes=["read"],
    )

    with pytest.raises(TokenError) as exc_info:
        await provider.exchange_refresh_token(registered_client, fake_token, scopes=["read"])
    assert exc_info.value.error == "invalid_grant"


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


# ------------------------------------------------------------------
# Redirect URI allowlist
# ------------------------------------------------------------------


@pytest.mark.parametrize("uri", [
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
    "https://chatgpt.com/connector_platform_oauth_redirect",
    "https://chatgpt.com/connector/oauth/qPYoR-UW7-xG",
    "http://localhost:53682/callback",
    "http://localhost:7777/oauth/callback",
    "http://127.0.0.1:8080/oauth/callback",
])
def test_is_allowed_redirect_uri_accepts_claude_and_loopback(uri: str) -> None:
    assert is_allowed_redirect_uri(uri)


@pytest.mark.parametrize("uri", [
    "https://attacker.example/cb",
    "https://claude.ai.attacker.example/api/mcp/auth_callback",
    "https://claude.ai/api/mcp/other",
    "https://localhost/callback",
    "http://localhost.attacker.example/callback",
    "https://chatgpt.com/connector/oauth/",
    "https://chatgpt.com/connector/oauth/id/../../evil",
    "https://chatgpt.com/connector/oauth/id?next=https://attacker.example",
    "https://chatgpt.com:8443/connector/oauth/id",
    "https://chatgpt.com.attacker.example/connector/oauth/id",
    "https://evil.chatgpt.com/connector/oauth/id",
])
def test_is_allowed_redirect_uri_rejects_others(uri: str) -> None:
    assert not is_allowed_redirect_uri(uri)


@pytest.mark.asyncio
async def test_register_client_rejects_foreign_redirect_uri(
    provider: VizzHubOAuthProvider,
    session_maker,
) -> None:
    client_info = OAuthClientInformationFull(
        client_id="rogue-client",
        client_secret="rogue-secret",
        redirect_uris=["http://localhost:3000/callback", "https://attacker.example/cb"],
    )

    with pytest.raises(RegistrationError) as exc_info:
        await provider.register_client(client_info)

    assert exc_info.value.error == "invalid_redirect_uri"
    async with session_maker() as session:
        row = await session.get(MCPOAuthClientDB, "rogue-client")
    assert row is None


@pytest.mark.asyncio
async def test_get_client_hides_legacy_client_with_foreign_redirect_uri(
    provider: VizzHubOAuthProvider,
    session_maker,
) -> None:
    info = {**_client_info_dict(), "client_id": "legacy-rogue",
            "redirect_uris": ["https://attacker.example/cb"]}
    async with session_maker() as session:
        session.add(MCPOAuthClientDB(
            client_id="legacy-rogue", client_secret="x", client_info=info,
        ))
        await session.commit()

    assert await provider.get_client("legacy-rogue") is None


@pytest.mark.asyncio
async def test_get_client_returns_none_for_invalid_stored_metadata(
    provider: VizzHubOAuthProvider,
    session_maker,
) -> None:
    info = {**_client_info_dict(), "client_id": "no-uris", "redirect_uris": []}
    async with session_maker() as session:
        session.add(MCPOAuthClientDB(client_id="no-uris", client_secret="x", client_info=info))
        await session.commit()

    assert await provider.get_client("no-uris") is None


# ------------------------------------------------------------------
# Resource indicator (RFC 8707)
# ------------------------------------------------------------------


def _authorize_params(resource: str | None) -> AuthorizationParams:
    return AuthorizationParams(
        state="s",
        scopes=["read"],
        code_challenge="c",
        redirect_uri="http://localhost:3000/callback",
        redirect_uri_provided_explicitly=True,
        resource=resource,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("resource", [None, BASE_URL, BASE_URL + "/"])
async def test_authorize_accepts_own_resource(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    resource: str | None,
) -> None:
    url = await provider.authorize(registered_client, _authorize_params(resource))
    assert "accounts.google.com" in url


@pytest.mark.asyncio
async def test_authorize_rejects_foreign_resource(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
) -> None:
    with pytest.raises(AuthorizeError) as exc_info:
        await provider.authorize(
            registered_client, _authorize_params("https://other.example/mcp"),
        )
    assert exc_info.value.error == "invalid_request"


# ------------------------------------------------------------------
# Deactivated users and single-use grants
# ------------------------------------------------------------------


def _auth_code_for(row: MCPOAuthCodeDB) -> AuthorizationCode:
    return AuthorizationCode(
        code=row.code,
        client_id=row.client_id,
        code_challenge=row.code_challenge,
        redirect_uri=row.redirect_uri,
        redirect_uri_provided_explicitly=True,
        scopes=["read"],
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp(),
    )


async def _deactivate(session_maker, user_id: uuid.UUID) -> None:
    async with session_maker() as session:
        user = await session.get(UserDB, user_id)
        user.active = False
        await session.commit()


@pytest.mark.asyncio
async def test_exchange_authorization_code_rejects_inactive_user(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    code_row_with_user: MCPOAuthCodeDB,
    session_maker,
    test_user_id: uuid.UUID,
) -> None:
    await _deactivate(session_maker, test_user_id)

    with pytest.raises(TokenError) as exc_info:
        await provider.exchange_authorization_code(
            registered_client, _auth_code_for(code_row_with_user),
        )

    assert exc_info.value.error == "invalid_grant"
    async with session_maker() as session:
        tokens = (await session.execute(select(MCPOAuthRefreshTokenDB))).scalars().all()
    assert tokens == []


@pytest.mark.asyncio
async def test_exchange_refresh_token_rejects_inactive_user_and_drops_token(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    refresh_token_row: MCPOAuthRefreshTokenDB,
    session_maker,
    test_user_id: uuid.UUID,
) -> None:
    await _deactivate(session_maker, test_user_id)
    token = RefreshToken(token=refresh_token_row.token, client_id=TEST_CLIENT_ID, scopes=["read"])

    with pytest.raises(TokenError) as exc_info:
        await provider.exchange_refresh_token(registered_client, token, scopes=[])

    assert exc_info.value.error == "invalid_grant"
    async with session_maker() as session:
        assert await session.get(MCPOAuthRefreshTokenDB, refresh_token_row.token) is None


@pytest.mark.asyncio
async def test_exchange_refresh_token_rejects_legacy_row_without_user(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    session_maker,
) -> None:
    async with session_maker() as session:
        session.add(MCPOAuthRefreshTokenDB(
            token="legacy-no-user",
            client_id=TEST_CLIENT_ID,
            user_id=None,
            user_email="old@vizzuality.com",
            scopes=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        ))
        await session.commit()
    token = RefreshToken(token="legacy-no-user", client_id=TEST_CLIENT_ID, scopes=["read"])

    with pytest.raises(TokenError):
        await provider.exchange_refresh_token(registered_client, token, scopes=[])


@pytest.mark.asyncio
async def test_concurrent_code_redemption_issues_tokens_once(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    code_row_with_user: MCPOAuthCodeDB,
) -> None:
    import asyncio

    auth_code = _auth_code_for(code_row_with_user)
    results = await asyncio.gather(
        provider.exchange_authorization_code(registered_client, auth_code),
        provider.exchange_authorization_code(registered_client, auth_code),
        return_exceptions=True,
    )

    assert sum(not isinstance(r, Exception) for r in results) == 1
    assert sum(isinstance(r, TokenError) for r in results) == 1


@pytest.mark.asyncio
async def test_concurrent_refresh_rotation_issues_tokens_once(
    provider: VizzHubOAuthProvider,
    registered_client: OAuthClientInformationFull,
    refresh_token_row: MCPOAuthRefreshTokenDB,
) -> None:
    import asyncio

    token = RefreshToken(token=refresh_token_row.token, client_id=TEST_CLIENT_ID, scopes=["read"])
    results = await asyncio.gather(
        provider.exchange_refresh_token(registered_client, token, scopes=[]),
        provider.exchange_refresh_token(registered_client, token, scopes=[]),
        return_exceptions=True,
    )

    assert sum(not isinstance(r, Exception) for r in results) == 1
    assert sum(isinstance(r, TokenError) for r in results) == 1
