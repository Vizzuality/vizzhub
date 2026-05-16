"""Dependabot alerts check job.

Daily cron job that checks every active project for new Dependabot alerts,
re-notifies unresolved high/critical ones on cadence, and marks closed
alerts as resolved. Per-alert-type logic lives in `app/worker/dependabot/`.
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.notifications.models.slack import AlertDefinitionDB
from app.modules.notifications.services.alert_service import AlertService
from app.modules.scorecard.services.collectors.dependabot import DependabotCollector
from app.utils.slack import get_slack_bot_token
from app.worker.dependabot.reminders import send_reminders
from app.worker.dependabot.shared import ALERT_NAME
from app.worker.dependabot.tracking import (
    backfill_manifest_paths,
    get_tracked_alerts,
    mark_alerts_resolved,
    notify_new_alert,
)
from app.worker.utils import complete_job_run, complete_with_error, start_job_run

logger = structlog.get_logger()


async def check_dependabot_alerts(ctx: dict) -> dict[str, Any]:
    """Check all projects for new Dependabot alerts and send notifications."""
    db: AsyncSession = ctx["db"]
    job_run = await start_job_run(db, "check_dependabot_alerts")
    logger.info("job_started", job_name="check_dependabot_alerts", job_run_id=str(job_run.id))

    try:
        bot_token = await get_slack_bot_token(db)
        if not bot_token:
            return await complete_with_error(
                db, job_run, "Slack not configured - missing bot token"
            )

        github_token = await IntegrationTokenService.get_token(db, "github")
        if not github_token:
            return await complete_with_error(
                db, job_run, "GitHub token not configured"
            )

        alert_definition = await _get_alert_definition(db)
        if not alert_definition:
            return await complete_with_error(
                db, job_run, f"Alert definition '{ALERT_NAME}' not found or disabled"
            )

        projects = await _get_eligible_projects(db)
        logger.info("projects_found", count=len(projects))

        project_snapshots = [(p, p.id, p.name) for p in projects]

        projects_checked = 0
        alerts_sent = 0

        for project, _project_id, project_name in project_snapshots:
            try:
                projects_checked += 1

                is_silenced = await AlertService.is_silenced(
                    db, project.id, alert_definition.id
                )
                if is_silenced:
                    logger.debug("project_silenced", project=project_name)
                    continue

                sent = await _process_project(
                    db, project, alert_definition, bot_token, github_token
                )
                alerts_sent += sent

            except Exception:
                await db.rollback()
                logger.exception("project_processing_failed", project=project_name)
                continue

        job_run.projects_checked = projects_checked
        job_run.alerts_sent = alerts_sent
        await complete_job_run(db, job_run)

        logger.info(
            "job_completed",
            projects_checked=projects_checked,
            alerts_sent=alerts_sent,
        )

        return {
            "status": "completed",
            "job_run_id": job_run.id,
            "projects_checked": projects_checked,
            "alerts_sent": alerts_sent,
        }

    except Exception as e:
        logger.exception("job_failed")
        return await complete_with_error(db, job_run, str(e))


async def _get_alert_definition(db: AsyncSession) -> AlertDefinitionDB | None:
    """Enabled dependabot alert definition, or None."""
    result = await db.execute(
        select(AlertDefinitionDB).where(
            AlertDefinitionDB.name == ALERT_NAME,
            AlertDefinitionDB.is_enabled.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _get_eligible_projects(db: AsyncSession) -> list[ProjectDB]:
    """Live projects with GitHub repo, Slack channel, and dependabot alerts enabled."""
    result = await db.execute(
        select(ProjectDB).where(
            ProjectDB.github_repo.isnot(None),
            ProjectDB.slack_channel_id.isnot(None),
            ProjectDB.status == "live",
            ProjectDB.has_dependabot_alerts.is_(True),
        )
    )
    return list(result.scalars().all())


async def _process_project(
    db: AsyncSession,
    project: ProjectDB,
    alert_definition: AlertDefinitionDB,
    bot_token: str,
    github_token: str,
) -> int:
    """Fetch GitHub alerts; diff against tracked rows; notify/remind/resolve."""
    current_alerts = await DependabotCollector.fetch_alerts(
        project.github_repo, github_token
    )
    current_alert_ids = {alert["number"] for alert in current_alerts}

    tracked_alerts = await get_tracked_alerts(db, project.id)
    tracked_alert_ids = {
        ta.github_alert_id for ta in tracked_alerts if not ta.resolved_at
    }
    new_alert_ids = current_alert_ids - tracked_alert_ids

    await backfill_manifest_paths(db, tracked_alerts, current_alerts)

    alerts_sent = 0
    for alert in current_alerts:
        if alert["number"] in new_alert_ids:
            sent = await notify_new_alert(
                db, project, alert_definition, bot_token, alert
            )
            if sent:
                alerts_sent += 1

    alerts_sent += await send_reminders(
        db, project, alert_definition, bot_token, tracked_alerts, current_alerts
    )

    resolved_ids = tracked_alert_ids - current_alert_ids
    if resolved_ids:
        await mark_alerts_resolved(db, project.id, resolved_ids)

    return alerts_sent
