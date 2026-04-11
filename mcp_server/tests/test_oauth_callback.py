"""Tests for Google OAuth callback — the SSO bridge between Google and MCP."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.routing import Route

from app.core.models.mcp_oauth import MCPOAuthClientDB, MCPOAuthCodeDB
from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import UserDB
from app.database import Base
from mcp_server.auth.callback import build_google_oauth_callback
from mcp_server.tests.conftest import TEST_DATABASE_URL

EXCHANGE_PATCH_TARGET = "mcp_server.auth.callback._exchange_google_code"
VERIFY_PATCH_TARGET = "mcp_server.auth.callback.id_token.verify_oauth2_token"

GOOGLE_CLIENT_ID = "test-google-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "test-google-client-secret"
ALLOWED_DOMAIN = "vizzuality.com"
BASE_URL = "https://hub.vizzuality.com/mcp"
TEST_MCP_CLIENT_ID = "test-mcp-client"
TEST_REDIRECT_URI = "http://localhost:3000/callback"


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
async def registered_client(session_maker) -> str:
    """Insert a pre-registered MCP OAuth client and return its client_id."""
    from mcp.shared.auth import OAuthClientInformationFull

    client_info = OAuthClientInformationFull(
        client_id=TEST_MCP_CLIENT_ID,
        client_secret="test-mcp-secret",
        redirect_uris=[TEST_REDIRECT_URI],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        client_name="Test MCP Client",
        token_endpoint_auth_method="client_secret_post",
    )
    async with session_maker() as session:
        session.add(
            MCPOAuthClientDB(
                client_id=TEST_MCP_CLIENT_ID,
                client_secret="test-mcp-secret",
                client_info=client_info.model_dump(mode="json"),
            )
        )
        await session.commit()
    return TEST_MCP_CLIENT_ID


@pytest_asyncio.fixture
async def test_user(session_maker, registered_client) -> UserDB:
    """Create a user and roles in the DB."""
    user_id = uuid.uuid4()
    async with session_maker() as session:
        user = UserDB(
            id=user_id,
            email="alice@vizzuality.com",
            first_name="Alice",
            last_name="Smith",
            active=True,
        )
        session.add(user)
        role = RoleDB(id=uuid.uuid4(), name="user", description="Default role")
        session.add(role)
        await session.flush()
        session.add(UserRoleDB(user_id=user_id, role_id=role.id))
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def inactive_user(session_maker, registered_client) -> UserDB:
    """Create an inactive user."""
    user_id = uuid.uuid4()
    async with session_maker() as session:
        user = UserDB(
            id=user_id,
            email="inactive@vizzuality.com",
            first_name="Gone",
            last_name="User",
            active=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def original_code_row(session_maker, registered_client) -> MCPOAuthCodeDB:
    """Insert the original auth code row (as created by authorize())."""
    async with session_maker() as session:
        row = MCPOAuthCodeDB(
            code="original-state-code-abc123",
            client_id=TEST_MCP_CLIENT_ID,
            code_challenge="test-pkce-challenge-xyz",
            redirect_uri=TEST_REDIRECT_URI,
            redirect_uri_provided_explicitly=True,
            scopes=["read"],
            resource="https://hub.vizzuality.com/mcp",
            mcp_state="mcp-client-original-state",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


def _google_exchange_ok(
    id_token_val: str = "mock.id.token",
) -> tuple[int, dict]:
    """Successful Google token exchange return value."""
    return (200, {"id_token": id_token_val, "access_token": "mock-access"})


def _google_exchange_fail() -> tuple[int, dict]:
    """Failed Google token exchange return value."""
    return (400, {"error": "invalid_grant"})


def _mock_idinfo(email: str = "alice@vizzuality.com") -> dict:
    """Build a mock Google ID token payload."""
    return {
        "email": email,
        "given_name": "Alice",
        "family_name": "Smith",
        "picture": "https://lh3.googleusercontent.com/photo.jpg",
    }


def _build_app(session_maker) -> Starlette:
    """Build a minimal Starlette app with just the callback route."""
    callback_fn = build_google_oauth_callback(
        session_maker=session_maker,
        google_client_id=GOOGLE_CLIENT_ID,
        google_client_secret=GOOGLE_CLIENT_SECRET,
        allowed_google_domain=ALLOWED_DOMAIN,
        base_url=BASE_URL,
    )
    return Starlette(routes=[Route("/oauth/callback", callback_fn)])


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_missing_params_returns_error(session_maker):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/oauth/callback", follow_redirects=False)

    assert response.status_code == 400
    assert "Missing required parameters" in response.text


@pytest.mark.asyncio
async def test_callback_missing_code_returns_error(session_maker):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/oauth/callback?state=some-state", follow_redirects=False
        )

    assert response.status_code == 400
    assert "Missing required parameters" in response.text


@pytest.mark.asyncio
async def test_callback_invalid_state_returns_error(session_maker, registered_client):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/oauth/callback?code=google-code&state=nonexistent-state",
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Invalid or expired session" in response.text


@pytest.mark.asyncio
async def test_callback_expired_state_returns_error(session_maker, registered_client):
    async with session_maker() as session:
        session.add(
            MCPOAuthCodeDB(
                code="expired-state-code",
                client_id=TEST_MCP_CLIENT_ID,
                code_challenge="challenge",
                redirect_uri=TEST_REDIRECT_URI,
                redirect_uri_provided_explicitly=True,
                scopes=["read"],
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        await session.commit()

    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/oauth/callback?code=google-code&state=expired-state-code",
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "expired" in response.text.lower()


@pytest.mark.asyncio
async def test_callback_google_token_exchange_failure(session_maker, original_code_row):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    with patch(EXCHANGE_PATCH_TARGET, new_callable=AsyncMock, return_value=_google_exchange_fail()):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/oauth/callback?code=bad-google-code&state={original_code_row.code}",
                follow_redirects=False,
            )

    assert response.status_code == 400
    assert "Failed to authenticate with Google" in response.text


@pytest.mark.asyncio
async def test_callback_wrong_domain_returns_error(session_maker, original_code_row):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    with (
        patch(EXCHANGE_PATCH_TARGET, new_callable=AsyncMock, return_value=_google_exchange_ok()),
        patch(VERIFY_PATCH_TARGET, return_value=_mock_idinfo(email="user@other-domain.com")),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/oauth/callback?code=google-code&state={original_code_row.code}",
                follow_redirects=False,
            )

    assert response.status_code == 400
    assert "Unauthorized domain" in response.text


@pytest.mark.asyncio
async def test_callback_unknown_user_returns_error(session_maker, original_code_row):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    with (
        patch(EXCHANGE_PATCH_TARGET, new_callable=AsyncMock, return_value=_google_exchange_ok()),
        patch(VERIFY_PATCH_TARGET, return_value=_mock_idinfo(email="nobody@vizzuality.com")),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/oauth/callback?code=google-code&state={original_code_row.code}",
                follow_redirects=False,
            )

    assert response.status_code == 400
    assert "User not found" in response.text


@pytest.mark.asyncio
async def test_callback_inactive_user_returns_error(
    session_maker, original_code_row, inactive_user,
):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    with (
        patch(EXCHANGE_PATCH_TARGET, new_callable=AsyncMock, return_value=_google_exchange_ok()),
        patch(VERIFY_PATCH_TARGET, return_value=_mock_idinfo(email="inactive@vizzuality.com")),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/oauth/callback?code=google-code&state={original_code_row.code}",
                follow_redirects=False,
            )

    assert response.status_code == 400
    assert "deactivated" in response.text.lower()


@pytest.mark.asyncio
async def test_callback_success_redirects_with_new_code(
    session_maker, original_code_row, test_user,
):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    with (
        patch(EXCHANGE_PATCH_TARGET, new_callable=AsyncMock, return_value=_google_exchange_ok()),
        patch(VERIFY_PATCH_TARGET, return_value=_mock_idinfo(email="alice@vizzuality.com")),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/oauth/callback?code=google-code&state={original_code_row.code}",
                follow_redirects=False,
            )

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(TEST_REDIRECT_URI)
    assert "code=" in location
    assert "state=mcp-client-original-state" in location


@pytest.mark.asyncio
async def test_callback_success_creates_new_code_row(
    session_maker, original_code_row, test_user,
):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    with (
        patch(EXCHANGE_PATCH_TARGET, new_callable=AsyncMock, return_value=_google_exchange_ok()),
        patch(VERIFY_PATCH_TARGET, return_value=_mock_idinfo(email="alice@vizzuality.com")),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/oauth/callback?code=google-code&state={original_code_row.code}",
                follow_redirects=False,
            )

    assert response.status_code == 302

    # Extract the new code from redirect location
    parsed = urlparse(response.headers["location"])
    new_code = parse_qs(parsed.query)["code"][0]

    # Verify the new code row has user info
    async with session_maker() as session:
        result = await session.execute(
            select(MCPOAuthCodeDB).where(MCPOAuthCodeDB.code == new_code)
        )
        new_row = result.scalar_one_or_none()

    assert new_row is not None
    assert new_row.user_email == "alice@vizzuality.com"
    assert new_row.user_id == test_user.id
    assert new_row.user_roles == ["user"]
    assert new_row.client_id == TEST_MCP_CLIENT_ID
    assert new_row.code_challenge == "test-pkce-challenge-xyz"
    assert new_row.redirect_uri == TEST_REDIRECT_URI
    assert new_row.scopes == ["read"]
    assert new_row.resource == "https://hub.vizzuality.com/mcp"
    assert new_row.mcp_state == "mcp-client-original-state"


@pytest.mark.asyncio
async def test_callback_success_deletes_original_row(
    session_maker, original_code_row, test_user,
):
    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    with (
        patch(EXCHANGE_PATCH_TARGET, new_callable=AsyncMock, return_value=_google_exchange_ok()),
        patch(VERIFY_PATCH_TARGET, return_value=_mock_idinfo(email="alice@vizzuality.com")),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/oauth/callback?code=google-code&state={original_code_row.code}",
                follow_redirects=False,
            )

    assert response.status_code == 302

    # The original row should be deleted
    async with session_maker() as session:
        result = await session.execute(
            select(MCPOAuthCodeDB).where(
                MCPOAuthCodeDB.code == original_code_row.code
            )
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_callback_success_without_mcp_state(
    session_maker, registered_client, test_user,
):
    """When mcp_state is None, the redirect omits the state param."""
    async with session_maker() as session:
        session.add(
            MCPOAuthCodeDB(
                code="no-state-code-abc",
                client_id=TEST_MCP_CLIENT_ID,
                code_challenge="challenge-no-state",
                redirect_uri=TEST_REDIRECT_URI,
                redirect_uri_provided_explicitly=True,
                scopes=["read"],
                mcp_state=None,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        await session.commit()

    app = _build_app(session_maker)
    transport = httpx.ASGITransport(app=app)

    with (
        patch(EXCHANGE_PATCH_TARGET, new_callable=AsyncMock, return_value=_google_exchange_ok()),
        patch(VERIFY_PATCH_TARGET, return_value=_mock_idinfo(email="alice@vizzuality.com")),
    ):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/oauth/callback?code=google-code&state=no-state-code-abc",
                follow_redirects=False,
            )

    assert response.status_code == 302
    location = response.headers["location"]
    assert "code=" in location
    assert "state=" not in location
