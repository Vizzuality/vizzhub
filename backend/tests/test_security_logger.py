"""Tests for security logging functionality.

This module tests the security logger which provides structured JSON logging
for security events including authentication, authorization, OAuth flows,
and suspicious activity detection.
"""

import json
from io import StringIO

import pytest

from app.core.security_logger import (
    SecurityEventHandler,
    log_auth_failure,
    log_auth_success,
    log_authorization_failure,
    log_oauth_state_validation_failed,
    log_oauth_token_issued,
    log_rate_limit_exceeded,
    security_logger,
)


class TestJSONLogging:
    """Test JSON logging format for security events."""

    def test_security_event_handler_emits_json(self) -> None:
        """Events should be logged as valid JSON."""
        handler = SecurityEventHandler()
        output = StringIO()

        # Redirect handler output to StringIO
        import sys

        old_stdout = sys.stdout
        sys.stdout = output

        try:
            # Create a mock log record
            import logging

            record = logging.LogRecord(
                name="security",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="Test event",
                args=(),
                exc_info=None,
            )
            record.event_type = "test_event"
            record.user_id = "user-123"
            record.ip_address = "192.168.1.1"

            handler.emit(record)

            # Verify output is valid JSON
            output_value = output.getvalue()
            parsed = json.loads(output_value.strip())

            assert isinstance(parsed, dict)
            assert "timestamp" in parsed
            assert "event_type" in parsed
            assert "details" in parsed

        finally:
            sys.stdout = old_stdout


class TestAuthEvents:
    """Test authentication event logging."""

    def test_log_auth_success_includes_user_and_ip(self, capfd) -> None:
        """log_auth_success should log user_id and ip_address."""
        log_auth_success("user-789", "10.0.0.1")

        captured = capfd.readouterr()
        parsed = json.loads(captured.out.strip())

        assert parsed["event_type"] == "auth_success"
        assert parsed["user_id"] == "user-789"
        assert parsed["ip_address"] == "10.0.0.1"
        assert "successful" in parsed["details"].lower()

    def test_log_auth_failure_includes_reason(self, capfd) -> None:
        """log_auth_failure should log failure reason."""
        log_auth_failure("test-user", "192.168.1.100", "Invalid password")

        captured = capfd.readouterr()
        parsed = json.loads(captured.out.strip())

        assert parsed["event_type"] == "auth_failure"
        assert parsed["user_id"] == "test-user"
        assert parsed["ip_address"] == "192.168.1.100"
        assert "Invalid password" in parsed["details"]
        assert parsed["severity"] == "WARNING"


class TestOAuthEvents:
    """Test OAuth event logging."""

    def test_log_oauth_token_issued_logs_provider(self, capfd) -> None:
        """log_oauth_token_issued should log OAuth provider."""
        log_oauth_token_issued("jira", "system", "172.16.0.1")

        captured = capfd.readouterr()
        parsed = json.loads(captured.out.strip())

        assert parsed["event_type"] == "oauth_token_issued"
        assert "jira" in parsed["details"]
        assert parsed["user_id"] == "system"
        assert parsed["ip_address"] == "172.16.0.1"

    def test_log_oauth_state_validation_failed_logs_reason(self, capfd) -> None:
        """log_oauth_state_validation_failed should log CSRF attempt details."""
        log_oauth_state_validation_failed(
            "203.0.113.1", "State mismatch - possible CSRF attack"
        )

        captured = capfd.readouterr()
        parsed = json.loads(captured.out.strip())

        assert parsed["event_type"] == "oauth_csrf_attempt"
        assert parsed["ip_address"] == "203.0.113.1"
        assert "CSRF" in parsed["details"]
        assert parsed["severity"] == "WARNING"


class TestSecurityEvents:
    """Test security violation event logging."""

    def test_log_rate_limit_exceeded_logs_endpoint(self, capfd) -> None:
        """log_rate_limit_exceeded should log rate limit violation."""
        log_rate_limit_exceeded("192.0.2.1", "/api/projects")

        captured = capfd.readouterr()
        parsed = json.loads(captured.out.strip())

        assert parsed["event_type"] == "rate_limit_exceeded"
        assert parsed["ip_address"] == "192.0.2.1"
        assert "/api/projects" in parsed["details"]
        assert parsed["severity"] == "WARNING"

    def test_log_authorization_failure_logs_resource(self, capfd) -> None:
        """log_authorization_failure should log authz failure."""
        log_authorization_failure("user-999", "10.1.1.1", "/admin/settings")

        captured = capfd.readouterr()
        parsed = json.loads(captured.out.strip())

        assert parsed["event_type"] == "authz_failure"
        assert parsed["user_id"] == "user-999"
        assert parsed["ip_address"] == "10.1.1.1"
        assert "/admin/settings" in parsed["details"]
        assert parsed["severity"] == "WARNING"
