"""Tests for security logging functionality.

This module tests the security logger which provides structured logging
for security events including OAuth flows and suspicious activity detection.
"""

import logging

import pytest

from app.core.security_logger import (
    log_oauth_state_validation_failed,
    log_oauth_token_issued,
    log_oauth_token_refresh,
    log_suspicious_activity,
)


class TestOAuthEvents:
    """Test OAuth event logging."""

    def test_log_oauth_token_issued(self, caplog: pytest.LogCaptureFixture) -> None:
        """log_oauth_token_issued should log provider, user, and IP."""
        with caplog.at_level(logging.INFO, logger="security"):
            log_oauth_token_issued("jira", "system", "172.16.0.1")

        assert len(caplog.records) == 1
        msg = str(caplog.records[0].message)
        assert "auth_oauth_token_issued" in msg

    def test_log_oauth_token_refresh(self, caplog: pytest.LogCaptureFixture) -> None:
        """log_oauth_token_refresh should log provider, user, and IP."""
        with caplog.at_level(logging.INFO, logger="security"):
            log_oauth_token_refresh("github", "user-456", "10.0.0.1")

        assert len(caplog.records) == 1
        msg = str(caplog.records[0].message)
        assert "auth_oauth_token_refreshed" in msg

    def test_log_oauth_state_validation_failed(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """log_oauth_state_validation_failed should log CSRF attempt details."""
        with caplog.at_level(logging.WARNING, logger="security"):
            log_oauth_state_validation_failed(
                "203.0.113.1",
                "State mismatch - possible CSRF attack",
            )

        assert len(caplog.records) == 1
        msg = str(caplog.records[0].message)
        assert "auth_csrf_attempt" in msg


class TestSuspiciousActivity:
    """Test suspicious activity logging."""

    def test_log_suspicious_activity(self, caplog: pytest.LogCaptureFixture) -> None:
        """log_suspicious_activity should log description and IP."""
        with caplog.at_level(logging.WARNING, logger="security"):
            log_suspicious_activity("Multiple failed login attempts", "192.168.1.100")

        assert len(caplog.records) == 1
        msg = str(caplog.records[0].message)
        assert "auth_suspicious_activity" in msg
