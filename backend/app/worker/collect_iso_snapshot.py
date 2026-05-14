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
from app.modules.iso.services.review_service import create_review_for_snapshot
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

    providers: list[tuple[str, type, bool]] = [
        ("google_workspace", GoogleWorkspaceCollector, await _is_gw_connected(db)),
        ("github", GitHubCollector, await _is_github_connected(db)),
        ("jira", JiraCollector, await _is_jira_connected(db)),
    ]
    for name, collector_cls, connected in providers:
        if not connected:
            continue
        try:
            snapshot = await collector_cls(db).capture(run_mode="cron")
            review = await create_review_for_snapshot(db, snapshot)
            await db.commit()
            results[name] = {
                "snapshot_id": str(snapshot.id),
                "review_id": str(review.id),
            }
            logger.info(
                "snapshot_captured",
                provider=name,
                snapshot_id=str(snapshot.id),
                review_id=str(review.id),
            )
        except Exception as e:
            await db.rollback()
            logger.error("snapshot_failed", provider=name, error=str(e), exc_info=True)
            errors.append(f"{name}: {e}")

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
