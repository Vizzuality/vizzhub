"""Security event logging for audit and monitoring."""

import json
import logging
from datetime import datetime
from typing import Any

# Configure security logger
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)


class SecurityEventHandler(logging.Handler):
    """Custom handler for security events with structured logging."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a structured security log event."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": getattr(record, "event_type", "unknown"),
            "severity": record.levelname,
            "user_id": getattr(record, "user_id", None),
            "ip_address": getattr(record, "ip_address", None),
            "details": record.getMessage(),
        }
        # Log as JSON for easy parsing by SIEM systems
        print(json.dumps(event))


# Add handler to security logger
security_logger.addHandler(SecurityEventHandler())


def log_auth_success(user_id: str, ip: str) -> None:
    """Log successful authentication event."""
    security_logger.info(
        f"Authentication successful for user {user_id}",
        extra={"event_type": "auth_success", "user_id": user_id, "ip_address": ip},
    )


def log_auth_failure(username: str, ip: str, reason: str) -> None:
    """Log failed authentication attempt."""
    security_logger.warning(
        f"Authentication failed for {username}: {reason}",
        extra={"event_type": "auth_failure", "user_id": username, "ip_address": ip},
    )


def log_oauth_token_issued(provider: str, user_id: str, ip: str) -> None:
    """Log OAuth token issuance."""
    security_logger.info(
        f"OAuth token issued for {provider}",
        extra={
            "event_type": "oauth_token_issued",
            "user_id": user_id,
            "ip_address": ip,
        },
    )


def log_oauth_token_refresh(provider: str, user_id: str, ip: str) -> None:
    """Log OAuth token refresh."""
    security_logger.info(
        f"OAuth token refreshed for {provider}",
        extra={
            "event_type": "oauth_token_refresh",
            "user_id": user_id,
            "ip_address": ip,
        },
    )


def log_suspicious_activity(description: str, ip: str) -> None:
    """Log suspicious activity for investigation."""
    security_logger.warning(
        f"Suspicious activity detected: {description}",
        extra={"event_type": "suspicious_activity", "ip_address": ip},
    )


def log_oauth_state_validation_failed(ip: str, reason: str) -> None:
    """Log OAuth state validation failure (potential CSRF attempt)."""
    security_logger.warning(
        f"OAuth state validation failed: {reason}",
        extra={
            "event_type": "oauth_csrf_attempt",
            "ip_address": ip,
        },
    )


def log_rate_limit_exceeded(ip: str, endpoint: str) -> None:
    """Log rate limit exceeded event."""
    security_logger.warning(
        f"Rate limit exceeded for endpoint {endpoint}",
        extra={
            "event_type": "rate_limit_exceeded",
            "ip_address": ip,
        },
    )


def log_authorization_failure(user_id: str, ip: str, resource: str) -> None:
    """Log authorization failure (insufficient permissions)."""
    security_logger.warning(
        f"Authorization failed for user {user_id} accessing {resource}",
        extra={
            "event_type": "authz_failure",
            "user_id": user_id,
            "ip_address": ip,
        },
    )
