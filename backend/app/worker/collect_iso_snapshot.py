"""ISO access snapshot cron job."""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.iso.services.collectors.google_workspace import (
    GoogleWorkspaceCollector,
)
from app.modules.iso.services.collectors.github import (
    GitHubCollector,
)
from app.modules.iso.services.collectors.jira import JiraCollector
from app.core.services.oauth_service import OAuthService
from app.modules.iso.services.google_workspace_oauth import GoogleWorkspaceOAuth
from app.modules.scorecard.models.slack import ScheduledJobRunDB
from app.modules.scorecard.services.slack_service import SlackService
from app.utils.slack import get_slack_bot_token, get_slack_leadership_channel
from app.worker.utils import complete_with_error

logger = logging.getLogger(__name__)


async def collect_iso_snapshot(ctx: dict) -> dict:
    """Capture access snapshots for all connected providers.

    Called by ARQ cron (monthly) or triggered manually.
    Each provider runs independently -- one failure doesn't block the other.
    """
    db: AsyncSession = ctx["db"]

    job_run = ScheduledJobRunDB(
        job_name="collect_iso_snapshot",
        status="running",
        projects_checked=0,
        alerts_sent=0,
    )
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    results: dict[str, dict] = {}
    errors: list[str] = []

    # Google Workspace
    if await _is_gw_connected(db):
        try:
            collector = GoogleWorkspaceCollector(db)
            snapshot = await collector.capture(run_mode="cron")
            await db.commit()
            results["google_workspace"] = {"snapshot_id": str(snapshot.id)}
            logger.info("ISO GW snapshot captured: %s", snapshot.id)
        except Exception as e:
            error_msg = f"google_workspace: {e}"
            logger.error("ISO GW snapshot failed: %s", e, exc_info=True)
            errors.append(error_msg)

    # GitHub
    if await _is_github_connected(db):
        try:
            collector = GitHubCollector(db)
            snapshot = await collector.capture(run_mode="cron")
            await db.commit()
            results["github"] = {"snapshot_id": str(snapshot.id)}
            logger.info("ISO GitHub snapshot captured: %s", snapshot.id)
        except Exception as e:
            error_msg = f"github: {e}"
            logger.error("ISO GitHub snapshot failed: %s", e, exc_info=True)
            errors.append(error_msg)

    # Jira
    if await _is_jira_connected(db):
        try:
            collector = JiraCollector(db)
            snapshot = await collector.capture(run_mode="cron")
            await db.commit()
            results["jira"] = {"snapshot_id": str(snapshot.id)}
            logger.info("ISO Jira snapshot captured: %s", snapshot.id)
        except Exception as e:
            error_msg = f"jira: {e}"
            logger.error("ISO Jira snapshot failed: %s", e, exc_info=True)
            errors.append(error_msg)

    if errors:
        combined_error = "; ".join(errors)
        await send_iso_failure_alert(db, combined_error)

    if errors and not results:
        return await complete_with_error(db, job_run, "; ".join(errors))

    job_run.status = "completed"
    job_run.completed_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "status": "completed",
        "job_run_id": job_run.id,
        "providers": results,
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _is_gw_connected(db: AsyncSession) -> bool:
    status = await GoogleWorkspaceOAuth.get_status(db)
    return status.get("connected", False)


async def _is_jira_connected(db: AsyncSession) -> bool:
    token = await OAuthService.get_valid_jira_token(db)
    return token is not None


async def _is_github_connected(db: AsyncSession) -> bool:
    token = await IntegrationTokenService.get_token(db, "github")
    if not token:
        return False
    org_name = await IntegrationTokenService.get_setting(
        db, "github", "iso_org_name"
    )
    return bool(org_name)


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
            "Action required: Check provider connections in ISO settings."
        )

        await SlackService.send_message(
            bot_token,
            channel_id,
            message,
        )
        logger.info("ISO failure alert sent to Slack")
    except Exception:
        logger.exception("Failed to send ISO failure Slack alert")
