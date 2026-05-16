"""Shared I/O surface for dependabot helpers.

Centralises `SlackService` so tests can patch a single path
(`app.worker.dependabot.shared.SlackService.send_message`).
"""

from __future__ import annotations

import structlog

from app.modules.notifications.services.slack_service import SlackService  # noqa: F401 — re-exported for patching

logger = structlog.get_logger()

ALERT_NAME = "dependabot_high_critical"
NO_CVE = "No CVE"

# Reminder intervals by severity (days between successive Slack reminders).
REMINDER_DAYS = {
    "critical": 2,
    "high": 7,
}


async def slack_send(bot_token: str, channel_id: str, message: str) -> dict:
    """Thin wrapper around SlackService.send_message for test isolation."""
    return await SlackService.send_message(bot_token, channel_id, message)
