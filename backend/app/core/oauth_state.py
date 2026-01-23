"""OAuth state management for CSRF protection."""

import secrets
from datetime import datetime, timedelta, timezone


class OAuthStateManager:
    """
    Manages OAuth state tokens to prevent CSRF attacks.

    Note: In-memory storage is used for simplicity.
    For production, use Redis or another distributed cache.
    """

    # In-memory store: {state: expiry_time}
    _states: dict[str, datetime] = {}

    @staticmethod
    def generate_state() -> str:
        """
        Generate a cryptographically secure state token.

        Returns:
            URL-safe random token string
        """
        state = secrets.token_urlsafe(32)
        # Store with 10-minute expiration
        OAuthStateManager._states[state] = datetime.now(timezone.utc) + timedelta(minutes=10)
        return state

    @staticmethod
    def validate_state(state: str) -> bool:
        """
        Validate state token and remove if valid.

        Args:
            state: State token to validate

        Returns:
            True if state is valid and not expired, False otherwise
        """
        if state not in OAuthStateManager._states:
            return False

        expiry = OAuthStateManager._states[state]
        if datetime.now(timezone.utc) > expiry:
            # Expired - remove and return False
            del OAuthStateManager._states[state]
            return False

        # Valid - consume token (one-time use only)
        del OAuthStateManager._states[state]
        return True

    @staticmethod
    def cleanup_expired() -> int:
        """
        Remove expired states from storage.

        Returns:
            Number of expired states removed
        """
        now = datetime.now(timezone.utc)
        expired = [s for s, exp in OAuthStateManager._states.items() if now > exp]
        for state in expired:
            del OAuthStateManager._states[state]
        return len(expired)
