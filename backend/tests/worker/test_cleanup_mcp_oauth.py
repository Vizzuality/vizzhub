"""Tests for the MCP OAuth cleanup worker job."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.mcp_oauth import MCPOAuthClientDB, MCPOAuthCodeDB, MCPOAuthRefreshTokenDB
from app.worker.cleanup_mcp_oauth import cleanup_mcp_oauth


def _make_client(client_id: str) -> MCPOAuthClientDB:
    """Build a minimal MCPOAuthClientDB row (no expiry)."""
    return MCPOAuthClientDB(
        client_id=client_id,
        client_secret=None,
        client_info={"client_name": "test"},
    )


def _make_code(code: str, client_id: str, expires_at: datetime) -> MCPOAuthCodeDB:
    return MCPOAuthCodeDB(
        code=code,
        client_id=client_id,
        code_challenge="challenge",
        redirect_uri="http://localhost/callback",
        redirect_uri_provided_explicitly=True,
        expires_at=expires_at,
    )


def _make_refresh_token(token: str, client_id: str, expires_at: datetime) -> MCPOAuthRefreshTokenDB:
    return MCPOAuthRefreshTokenDB(
        token=token,
        client_id=client_id,
        expires_at=expires_at,
    )


@pytest.mark.asyncio
async def test_cleanup_deletes_expired_codes(db_session: AsyncSession) -> None:
    """Expired authorization codes are removed by the cleanup job."""
    now = datetime.now(timezone.utc)
    client = _make_client("client-codes-1")
    db_session.add(client)
    await db_session.flush()

    expired_code = _make_code("expired-code-1", client.client_id, now - timedelta(minutes=5))
    db_session.add(expired_code)
    await db_session.flush()

    await cleanup_mcp_oauth({"db": db_session})

    result = await db_session.execute(
        select(MCPOAuthCodeDB).where(MCPOAuthCodeDB.code == "expired-code-1")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cleanup_deletes_expired_refresh_tokens(db_session: AsyncSession) -> None:
    """Expired refresh tokens are removed by the cleanup job."""
    now = datetime.now(timezone.utc)
    client = _make_client("client-tokens-1")
    db_session.add(client)
    await db_session.flush()

    expired_token = _make_refresh_token("expired-token-1", client.client_id, now - timedelta(days=31))
    db_session.add(expired_token)
    await db_session.flush()

    await cleanup_mcp_oauth({"db": db_session})

    result = await db_session.execute(
        select(MCPOAuthRefreshTokenDB).where(MCPOAuthRefreshTokenDB.token == "expired-token-1")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cleanup_preserves_valid_entries(db_session: AsyncSession) -> None:
    """Non-expired codes and tokens are not affected by the cleanup job."""
    now = datetime.now(timezone.utc)
    client = _make_client("client-valid-1")
    db_session.add(client)
    await db_session.flush()

    valid_code = _make_code("valid-code-1", client.client_id, now + timedelta(seconds=30))
    valid_token = _make_refresh_token("valid-token-1", client.client_id, now + timedelta(days=29))
    db_session.add(valid_code)
    db_session.add(valid_token)
    await db_session.flush()

    await cleanup_mcp_oauth({"db": db_session})

    code_result = await db_session.execute(
        select(MCPOAuthCodeDB).where(MCPOAuthCodeDB.code == "valid-code-1")
    )
    token_result = await db_session.execute(
        select(MCPOAuthRefreshTokenDB).where(MCPOAuthRefreshTokenDB.token == "valid-token-1")
    )
    assert code_result.scalar_one_or_none() is not None
    assert token_result.scalar_one_or_none() is not None
