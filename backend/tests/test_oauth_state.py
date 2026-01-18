"""Tests for OAuth state manager CSRF protection.

This module tests the OAuthStateManager which prevents CSRF attacks
by generating, validating, and managing one-time-use state tokens.
"""

import time
from datetime import datetime, timedelta

import pytest

from app.core.oauth_state import OAuthStateManager


class TestOAuthStateGenerate:
    """Test OAuth state token generation."""

    def test_oauth_state_generate_returns_unique_tokens(self) -> None:
        """Each call to generate_state() should return different token."""
        # Clear any existing states
        OAuthStateManager._states.clear()

        # Generate two tokens
        state1 = OAuthStateManager.generate_state()
        state2 = OAuthStateManager.generate_state()

        # Tokens should be different
        assert state1 != state2
        # Both should be non-empty strings
        assert isinstance(state1, str)
        assert isinstance(state2, str)
        assert len(state1) > 0
        assert len(state2) > 0

    def test_oauth_state_generate_stores_with_expiration(self) -> None:
        """Token should be stored with 10-minute expiry."""
        # Clear existing states
        OAuthStateManager._states.clear()

        # Generate state and capture time
        before = datetime.utcnow()
        state = OAuthStateManager.generate_state()
        after = datetime.utcnow()

        # Token should be in storage
        assert state in OAuthStateManager._states

        # Expiry should be ~10 minutes from now
        expiry = OAuthStateManager._states[state]
        expected_min = before + timedelta(minutes=10)
        expected_max = after + timedelta(minutes=10)

        assert expected_min <= expiry <= expected_max


class TestOAuthStateValidate:
    """Test OAuth state token validation."""

    def test_oauth_state_validate_valid_token_returns_true(self) -> None:
        """Valid unexpired token should be accepted."""
        # Clear and generate fresh state
        OAuthStateManager._states.clear()
        state = OAuthStateManager.generate_state()

        # Validation should succeed
        assert OAuthStateManager.validate_state(state) is True

    def test_oauth_state_validate_invalid_token_returns_false(self) -> None:
        """Unknown token should be rejected."""
        # Clear all states
        OAuthStateManager._states.clear()

        # Try to validate token that was never generated
        result = OAuthStateManager.validate_state("unknown-token-12345")

        assert result is False

    def test_oauth_state_validate_expired_token_returns_false(self) -> None:
        """Expired token should be rejected."""
        # Clear and manually add expired token
        OAuthStateManager._states.clear()
        expired_state = "expired-token"
        OAuthStateManager._states[expired_state] = datetime.utcnow() - timedelta(
            minutes=1
        )

        # Validation should fail
        result = OAuthStateManager.validate_state(expired_state)

        assert result is False

    def test_oauth_state_validate_consumes_token_one_time_use(self) -> None:
        """Token should be deleted after successful validation (prevents replay)."""
        # Clear and generate state
        OAuthStateManager._states.clear()
        state = OAuthStateManager.generate_state()

        # First validation succeeds
        assert OAuthStateManager.validate_state(state) is True

        # Token should no longer be in storage
        assert state not in OAuthStateManager._states

    def test_oauth_state_validate_same_token_twice_fails(self) -> None:
        """Second use of same token should fail."""
        # Clear and generate state
        OAuthStateManager._states.clear()
        state = OAuthStateManager.generate_state()

        # First validation succeeds
        first_result = OAuthStateManager.validate_state(state)
        assert first_result is True

        # Second validation fails (token consumed)
        second_result = OAuthStateManager.validate_state(state)
        assert second_result is False


class TestOAuthStateCleanup:
    """Test OAuth state cleanup of expired tokens."""

    def test_oauth_state_cleanup_expired_removes_old_tokens(self) -> None:
        """cleanup_expired() should remove expired tokens."""
        # Clear and add expired tokens
        OAuthStateManager._states.clear()
        expired1 = "expired-1"
        expired2 = "expired-2"
        OAuthStateManager._states[expired1] = datetime.utcnow() - timedelta(minutes=5)
        OAuthStateManager._states[expired2] = datetime.utcnow() - timedelta(
            minutes=15
        )

        # Run cleanup
        removed_count = OAuthStateManager.cleanup_expired()

        # Both expired tokens should be removed
        assert removed_count == 2
        assert expired1 not in OAuthStateManager._states
        assert expired2 not in OAuthStateManager._states

    def test_oauth_state_cleanup_expired_keeps_valid_tokens(self) -> None:
        """cleanup_expired() should keep valid unexpired tokens."""
        # Clear and add mix of expired and valid tokens
        OAuthStateManager._states.clear()
        expired = "expired-token"
        valid = "valid-token"
        OAuthStateManager._states[expired] = datetime.utcnow() - timedelta(minutes=1)
        OAuthStateManager._states[valid] = datetime.utcnow() + timedelta(minutes=5)

        # Run cleanup
        removed_count = OAuthStateManager.cleanup_expired()

        # Only expired token should be removed
        assert removed_count == 1
        assert expired not in OAuthStateManager._states
        assert valid in OAuthStateManager._states

    def test_oauth_state_cleanup_expired_returns_count(self) -> None:
        """cleanup_expired() should return number of removed tokens."""
        # Clear and add expired tokens
        OAuthStateManager._states.clear()
        for i in range(5):
            token = f"expired-{i}"
            OAuthStateManager._states[token] = datetime.utcnow() - timedelta(
                minutes=i + 1
            )

        # Cleanup should return count of removed tokens
        removed_count = OAuthStateManager.cleanup_expired()

        assert removed_count == 5
        assert len(OAuthStateManager._states) == 0
