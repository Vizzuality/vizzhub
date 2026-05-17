"""Business alerts check job.

This cron job runs daily to check all active projects for business alert
conditions and sends Slack notifications to the leadership channel.

Alert types (one per module in `app/worker/business_alerts/`):
1. Budget exceeded (>=100% consumed)
2. Timeline at risk (velocity suggests won't complete by end_date)
3. Project overdue (>30 days past end_date)

Monthly throttling is enforced inside each evaluator via
`AlertService.was_notified_this_month`.
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import AlertDefinitionDB
from app.utils.slack import get_slack_bot_token, get_slack_leadership_channel
from app.worker.business_alerts.budget_exceeded import check_budget_exceeded
from app.worker.business_alerts.project_overdue import check_project_overdue
from app.worker.business_alerts.shared import ALERT_NAMES, get_latest_metrics
from app.worker.business_alerts.timeline_at_risk import check_timeline_at_risk
from app.worker.utils import complete_job_run, complete_with_error, start_job_run

logger = structlog.get_logger()


async def check_business_alerts(ctx: dict) -> dict[str, Any]:
    """Check all projects for business alert conditions and notify leadership.

    Returns:
        Dict with status, job_run_id, projects_checked, alerts_sent (and
        optionally error).
    """
    db: AsyncSession = ctx["db"]
    job_run = await start_job_run(db, "check_business_alerts")
    logger.info("job_started", job_name="check_business_alerts", job_run_id=str(job_run.id))

    try:
        bot_token = await get_slack_bot_token(db)
        if not bot_token:
            return await complete_with_error(
                db, job_run, "Slack not configured - missing bot token"
            )

        leadership_channel_id = await get_slack_leadership_channel(db)
        if not leadership_channel_id:
            return await complete_with_error(db, job_run, "Leadership channel not configured")

        alert_definitions = await _get_alert_definitions(db)
        if not alert_definitions:
            return await complete_with_error(
                db, job_run, "No business alert definitions found or enabled"
            )

        projects = await _get_active_projects(db)
        logger.info("projects_found", count=len(projects))

        # Snapshot every project's id + name up front. Any rollback inside
        # the loop expires the whole identity map; ORM attribute access from
        # a later iteration (or the except branch) would then need async IO
        # from a sync site and raise MissingGreenlet.
        project_snapshots = [(p, p.id, p.name) for p in projects]

        projects_checked = 0
        alerts_sent = 0

        for project, _project_id, project_name in project_snapshots:
            try:
                sent = await _process_project(
                    db,
                    project,
                    alert_definitions,
                    bot_token,
                    leadership_channel_id,
                )
                projects_checked += 1
                alerts_sent += sent

            except Exception:
                await db.rollback()
                logger.exception("project_processing_failed", project=project_name)
                projects_checked += 1
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


async def _get_alert_definitions(db: AsyncSession) -> dict[str, AlertDefinitionDB]:
    """Enabled business alert definitions, keyed by name."""
    result = await db.execute(
        select(AlertDefinitionDB).where(
            AlertDefinitionDB.category == "business",
            AlertDefinitionDB.is_enabled.is_(True),
        )
    )
    return {d.name: d for d in result.scalars().all()}


async def _get_active_projects(db: AsyncSession) -> list[ProjectDB]:
    """Live projects with budget alerts enabled."""
    result = await db.execute(
        select(ProjectDB).where(
            ProjectDB.status == "live",
            ProjectDB.has_budget_alerts.is_(True),
        )
    )
    return list(result.scalars().all())


async def _process_project(
    db: AsyncSession,
    project: ProjectDB,
    alert_definitions: dict[str, AlertDefinitionDB],
    bot_token: str,
    leadership_channel_id: str,
) -> int:
    """Dispatch each alert evaluator for `project`; return total alerts sent."""
    metrics = await get_latest_metrics(db, project.id)
    alerts_sent = 0

    if (budget_def := alert_definitions.get(ALERT_NAMES["budget_exceeded"])) and (
        await check_budget_exceeded(
            db, project, metrics, budget_def, bot_token, leadership_channel_id
        )
    ):
        alerts_sent += 1

    if (timeline_def := alert_definitions.get(ALERT_NAMES["timeline_at_risk"])) and (
        await check_timeline_at_risk(
            db, project, metrics, timeline_def, bot_token, leadership_channel_id
        )
    ):
        alerts_sent += 1

    if (overdue_def := alert_definitions.get(ALERT_NAMES["project_overdue"])) and (
        await check_project_overdue(db, project, overdue_def, bot_token, leadership_channel_id)
    ):
        alerts_sent += 1

    return alerts_sent
