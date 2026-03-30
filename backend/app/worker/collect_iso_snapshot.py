"""ISO access snapshot cron job."""

import structlog
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.core.services.oauth_service import OAuthService
from app.modules.iso.public import (
    GitHubCollector,
    GoogleWorkspaceCollector,
    GoogleWorkspaceOAuth,
    JiraCollector,
)
from app.modules.notifications.public import ScheduledJobRunDB, SlackService
from app.utils.slack import get_slack_bot_token, get_slack_leadership_channel
from app.worker.utils import complete_with_error

logger = structlog.get_logger()


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
            logger.info("snapshot_captured", provider="google_workspace", snapshot_id=str(snapshot.id))
        except Exception as e:
            error_msg = f"google_workspace: {e}"
            logger.error("snapshot_failed", provider="google_workspace", error=str(e), exc_info=True)
            errors.append(error_msg)

    # GitHub
    if await _is_github_connected(db):
        try:
            collector = GitHubCollector(db)
            snapshot = await collector.capture(run_mode="cron")
            await db.commit()
            results["github"] = {"snapshot_id": str(snapshot.id)}
            logger.info("snapshot_captured", provider="github", snapshot_id=str(snapshot.id))
        except Exception as e:
            error_msg = f"github: {e}"
            logger.error("snapshot_failed", provider="github", error=str(e), exc_info=True)
            errors.append(error_msg)

    # Jira
    if await _is_jira_connected(db):
        try:
            collector = JiraCollector(db)
            snapshot = await collector.capture(run_mode="cron")
            await db.commit()
            results["jira"] = {"snapshot_id": str(snapshot.id)}
            logger.info("snapshot_captured", provider="jira", snapshot_id=str(snapshot.id))
        except Exception as e:
            error_msg = f"jira: {e}"
            logger.error("snapshot_failed", provider="jira", error=str(e), exc_info=True)
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
            logger.warning("slack_not_configured")
            return
        channel_id = await get_slack_leadership_channel(db)
        if not channel_id:
            logger.warning("leadership_channel_not_configured")
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
        logger.info("iso_failure_alert_sent")
    except Exception:
        logger.exception("iso_failure_alert_send_failed")
