"""Tests for DB-backed OAuth state manager CSRF protection.

Tests that OAuth CSRF state tokens are stored in the database (not in-memory),
support multi-worker deployments, and enforce one-time use with TTL.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.oauth_state import OAuthStateManager
from app.models.oauth import OAuthStateDB


class TestOAuthStateGenerate:
    """Test OAuth state token generation."""

    @pytest.mark.asyncio
    async def test_generate_returns_unique_tokens(
        self, db_session: AsyncSession
    ) -> None:
        """Each call should return a different token."""
        state1 = await OAuthStateManager.generate_state(db_session)
        state2 = await OAuthStateManager.generate_state(db_session)

        assert state1 != state2
        assert isinstance(state1, str)
        assert len(state1) > 0

    @pytest.mark.asyncio
    async def test_generate_stores_in_db(self, db_session: AsyncSession) -> None:
        """Token should be persisted in oauth_states table."""
        state = await OAuthStateManager.generate_state(db_session)

        result = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == state)
        )
        row = result.scalar_one_or_none()
        assert row is not None

    @pytest.mark.asyncio
    async def test_generate_sets_10_minute_expiry(
        self, db_session: AsyncSession
    ) -> None:
        """Token should expire ~10 minutes from creation."""
        before = datetime.now(timezone.utc)
        state = await OAuthStateManager.generate_state(db_session)
        after = datetime.now(timezone.utc)

        result = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == state)
        )
        row = result.scalar_one()

        expected_min = before + timedelta(minutes=10)
        expected_max = after + timedelta(minutes=10)
        assert expected_min <= row.expires_at <= expected_max


class TestOAuthStateValidate:
    """Test OAuth state token validation."""

    @pytest.mark.asyncio
    async def test_validate_valid_token_returns_true(
        self, db_session: AsyncSession
    ) -> None:
        """Valid unexpired token should be accepted."""
        state = await OAuthStateManager.generate_state(db_session)
        assert await OAuthStateManager.validate_state(state, db_session) is True

    @pytest.mark.asyncio
    async def test_validate_unknown_token_returns_false(
        self, db_session: AsyncSession
    ) -> None:
        """Unknown token should be rejected."""
        result = await OAuthStateManager.validate_state(
            "unknown-token-12345", db_session
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_expired_token_returns_false(
        self, db_session: AsyncSession
    ) -> None:
        """Expired token should be rejected and deleted."""
        expired = OAuthStateDB(
            state="expired-token",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db_session.add(expired)
        await db_session.flush()

        result = await OAuthStateManager.validate_state("expired-token", db_session)
        assert result is False

        row = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == "expired-token")
        )
        assert row.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_validate_consumes_token(self, db_session: AsyncSession) -> None:
        """Token should be deleted after successful validation."""
        state = await OAuthStateManager.generate_state(db_session)
        assert await OAuthStateManager.validate_state(state, db_session) is True

        row = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == state)
        )
        assert row.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_validate_same_token_twice_fails(
        self, db_session: AsyncSession
    ) -> None:
        """Second use of same token should fail."""
        state = await OAuthStateManager.generate_state(db_session)
        assert await OAuthStateManager.validate_state(state, db_session) is True
        assert await OAuthStateManager.validate_state(state, db_session) is False


class TestOAuthStateCleanup:
    """Test cleanup of expired state tokens."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired(self, db_session: AsyncSession) -> None:
        """cleanup_expired should remove expired tokens."""
        db_session.add(
            OAuthStateDB(
                state="expired-1",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
        )
        db_session.add(
            OAuthStateDB(
                state="expired-2",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=15),
            )
        )
        await db_session.flush()

        removed = await OAuthStateManager.cleanup_expired(db_session)
        assert removed == 2

    @pytest.mark.asyncio
    async def test_cleanup_keeps_valid(self, db_session: AsyncSession) -> None:
        """cleanup_expired should keep valid unexpired tokens."""
        db_session.add(
            OAuthStateDB(
                state="expired",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        db_session.add(
            OAuthStateDB(
                state="valid",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            )
        )
        await db_session.flush()

        removed = await OAuthStateManager.cleanup_expired(db_session)
        assert removed == 1

        row = await db_session.execute(
            select(OAuthStateDB).where(OAuthStateDB.state == "valid")
        )
        assert row.scalar_one_or_none() is not None
