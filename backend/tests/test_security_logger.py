"""Tests for security logging functionality.

This module tests the security logger which provides structured JSON logging
for security events including OAuth flows and suspicious activity detection.
"""

import json
from io import StringIO

from app.core.security_logger import (
    SecurityEventHandler,
    log_oauth_state_validation_failed,
    log_oauth_token_issued,
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
