"""ISO access snapshot cron job."""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso.services.collectors.google_workspace import (
    GoogleWorkspaceCollector,
)
from app.services.slack_service import SlackService
from app.utils.slack import get_slack_bot_token, get_slack_leadership_channel

logger = logging.getLogger(__name__)


async def collect_iso_snapshot(ctx: dict) -> dict:
    """Capture a Google Workspace access snapshot.

    Called by ARQ cron (monthly) or triggered manually.
    On failure, sends Slack alert to leadership channel.
    """
    db: AsyncSession = ctx["db"]

    try:
        collector = GoogleWorkspaceCollector(db)
        snapshot = await collector.capture(run_mode="cron")
    except Exception as e:
        error_msg = str(e)
        logger.error(
            "ISO snapshot capture failed: %s",
            error_msg,
            exc_info=True,
        )
        await send_iso_failure_alert(db, error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    logger.info("ISO snapshot captured: %s", snapshot.id)
    return {
        "status": "completed",
        "snapshot_id": str(snapshot.id),
        "provider": snapshot.provider,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def send_iso_failure_alert(db: AsyncSession, error_message: str) -> None:
    """Send Slack notification when ISO snapshot capture fails."""
    try:
        bot_token = await get_slack_bot_token(db)
        if not bot_token:
            logger.warning("Slack not configured, cannot send ISO failure alert")
            return
        channel_id = await get_slack_leadership_channel(db)
        if not channel_id:
            logger.warning("No leadership channel configured for ISO failure alert")
            return

        message = (
            ":rotating_light: *ISO Access Review \u2014 Snapshot capture failed*\n"
            f"Error: {error_message}\n"
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            "Action required: Check Google Workspace OAuth connection in ISO settings."
        )

        await SlackService.send_message(
            bot_token,
            channel_id,
            message,
        )
        logger.info("ISO failure alert sent to Slack")
    except Exception:
        logger.exception("Failed to send ISO failure Slack alert")
