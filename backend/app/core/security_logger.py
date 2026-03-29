"""Security event logging for audit and monitoring."""

import structlog

security_logger = structlog.get_logger("security")


def log_oauth_token_issued(provider: str, user_id: str, ip: str) -> None:
    """Log OAuth token issuance."""
    security_logger.info(
        "auth_oauth_token_issued",
        provider=provider,
        user_id=user_id,
        ip_address=ip,
    )


def log_oauth_token_refresh(provider: str, user_id: str, ip: str) -> None:
    """Log OAuth token refresh."""
    security_logger.info(
        "auth_oauth_token_refreshed",
        provider=provider,
        user_id=user_id,
        ip_address=ip,
    )


def log_suspicious_activity(description: str, ip: str) -> None:
    """Log suspicious activity for investigation."""
    security_logger.warning(
        "auth_suspicious_activity",
        description=description,
        ip_address=ip,
    )


def log_oauth_state_validation_failed(ip: str, reason: str) -> None:
    """Log OAuth state validation failure (potential CSRF attempt)."""
    security_logger.warning(
        "auth_csrf_attempt",
        reason=reason,
        ip_address=ip,
    )
