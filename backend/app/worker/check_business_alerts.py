"""Business alerts check job.

This cron job runs daily to check all active projects for business alert
conditions and sends Slack notifications to the leadership channel.

Alert types:
1. Budget exceeded (>=100% consumed)
2. Timeline at risk (velocity suggests won't complete by end_date)
3. Project overdue (>30 days past end_date)

The job uses monthly throttling - only one notification per project per month
for each alert type.
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.models.metrics import MetricsDB, SnapshotType
from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import (
    AlertDefinitionDB,
    ScheduledJobRunDB,
)
from app.modules.notifications.services.alert_service import AlertService
from app.modules.notifications.services.slack_service import SlackService
from app.utils.slack import get_slack_bot_token, get_slack_leadership_channel
from app.worker.utils import complete_with_error

logger = logging.getLogger(__name__)

ALERT_NAMES = {
    "budget_exceeded": "budget_exceeded",
    "timeline_at_risk": "timeline_at_risk",
    "project_overdue": "project_overdue",
}

DEFAULT_GRACE_DAYS = 30
DAYS_PER_WEEK = 7
DEFAULT_WEEKS_FOR_VELOCITY = 4


async def check_business_alerts(ctx: dict) -> dict[str, Any]:
    """Check all projects for business alert conditions and send notifications.

    This job:
    1. Gets all active projects
    2. For each project, checks business alert conditions:
       - Budget exceeded (>=100%)
       - Timeline at risk (velocity-based)
       - Project overdue (>30 days past end_date)
    3. Sends notifications to leadership channel (monthly throttled)
    4. Logs all notifications

    Args:
        ctx: ARQ context containing database session

    Returns:
        Dictionary with job execution results including:
        - status: "completed" or "error"
        - job_run_id: ID of the ScheduledJobRunDB record
        - projects_checked: Number of projects processed
        - alerts_sent: Number of notifications sent
        - error: Error message if status is "error"
    """
    db: AsyncSession = ctx["db"]

    job_run = ScheduledJobRunDB(
        job_name="check_business_alerts",
        status="running",
        projects_checked=0,
        alerts_sent=0,
    )
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    try:
        bot_token = await get_slack_bot_token(db)
        if not bot_token:
            return await complete_with_error(
                db, job_run, "Slack not configured - missing bot token"
            )

        leadership_channel_id = await get_slack_leadership_channel(db)
        if not leadership_channel_id:
            return await complete_with_error(
                db, job_run, "Leadership channel not configured"
            )

        alert_definitions = await _get_alert_definitions(db)
        if not alert_definitions:
            return await complete_with_error(
                db, job_run, "No business alert definitions found or enabled"
            )

        projects = await _get_active_projects(db)
        logger.info(f"Found {len(projects)} active projects to check")

        projects_checked = 0
        alerts_sent = 0

        for project in projects:
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

            except Exception as e:
                logger.error(f"Error processing project {project.name}: {e}")
                projects_checked += 1
                continue

        job_run.status = "completed"
        job_run.projects_checked = projects_checked
        job_run.alerts_sent = alerts_sent
        job_run.completed_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            f"Business alerts check completed: {projects_checked} projects checked, "
            f"{alerts_sent} alerts sent"
        )

        return {
            "status": "completed",
            "job_run_id": job_run.id,
            "projects_checked": projects_checked,
            "alerts_sent": alerts_sent,
        }

    except Exception as e:
        logger.exception("Business alerts check job failed")
        return await complete_with_error(db, job_run, str(e))


async def _get_alert_definitions(db: AsyncSession) -> dict[str, AlertDefinitionDB]:
    """Get all enabled business alert definitions."""
    result = await db.execute(
        select(AlertDefinitionDB).where(
            AlertDefinitionDB.category == "business",
            AlertDefinitionDB.is_enabled.is_(True),
        )
    )
    definitions = result.scalars().all()
    return {d.name: d for d in definitions}


async def _get_active_projects(db: AsyncSession) -> list[ProjectDB]:
    """Get all live projects with budget alerts enabled."""
    result = await db.execute(
        select(ProjectDB).where(
            ProjectDB.status == "live",
            ProjectDB.has_budget_alerts.is_(True),
        )
    )
    return list(result.scalars().all())


async def _get_latest_metrics(db: AsyncSession, project_id: UUID) -> MetricsDB | None:
    """Get the latest cumulative metrics for a project."""
    result = await db.execute(
        select(MetricsDB)
        .where(
            MetricsDB.project_id == project_id,
            MetricsDB.snapshot_type == SnapshotType.CUMULATIVE.value,
        )
        .order_by(MetricsDB.period_year.desc(), MetricsDB.period_month.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _process_project(
    db: AsyncSession,
    project: ProjectDB,
    alert_definitions: dict[str, AlertDefinitionDB],
    bot_token: str,
    leadership_channel_id: str,
) -> int:
    """Process a single project for business alerts.

    Args:
        db: Database session
        project: Project to check
        alert_definitions: Dict of alert definitions by name
        bot_token: Slack bot token
        leadership_channel_id: Leadership Slack channel ID

    Returns:
        Number of alerts sent for this project
    """
    alerts_sent = 0

    metrics = await _get_latest_metrics(db, project.id)

    if ALERT_NAMES["budget_exceeded"] in alert_definitions:
        alert_def = alert_definitions[ALERT_NAMES["budget_exceeded"]]
        sent = await _check_budget_exceeded(
            db, project, metrics, alert_def, bot_token, leadership_channel_id
        )
        if sent:
            alerts_sent += 1

    if ALERT_NAMES["timeline_at_risk"] in alert_definitions:
        alert_def = alert_definitions[ALERT_NAMES["timeline_at_risk"]]
        sent = await _check_timeline_at_risk(
            db, project, metrics, alert_def, bot_token, leadership_channel_id
        )
        if sent:
            alerts_sent += 1

    if ALERT_NAMES["project_overdue"] in alert_definitions:
        alert_def = alert_definitions[ALERT_NAMES["project_overdue"]]
        sent = await _check_project_overdue(
            db, project, alert_def, bot_token, leadership_channel_id
        )
        if sent:
            alerts_sent += 1

    return alerts_sent


async def _check_budget_exceeded(
    db: AsyncSession,
    project: ProjectDB,
    metrics: MetricsDB | None,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    leadership_channel_id: str,
) -> bool:
    """Check if project budget is exceeded (>=100%) and send alert.

    Args:
        db: Database session
        project: Project to check
        metrics: Latest metrics for the project
        alert_def: Alert definition for budget exceeded
        bot_token: Slack bot token
        leadership_channel_id: Leadership channel ID

    Returns:
        True if alert was sent, False otherwise
    """
    if not metrics:
        return False

    if not metrics.budget_total or not metrics.cost_to_date:
        return False

    budget_total = Decimal(str(metrics.budget_total))
    cost_to_date = Decimal(str(metrics.cost_to_date))

    if budget_total <= 0:
        return False

    budget_percent = (cost_to_date / budget_total) * 100

    if budget_percent < 100:
        return False

    is_silenced = await AlertService.is_silenced(db, project.id, alert_def.id)
    if is_silenced:
        logger.debug(f"Skipping silenced project for budget alert: {project.name}")
        return False

    was_notified = await AlertService.was_notified_this_month(
        db, project.id, alert_def.id
    )
    if was_notified:
        logger.debug(f"Already notified this month for budget alert: {project.name}")
        return False

    template = await AlertService.get_template(db, alert_def.id, "initial")
    if not template:
        template = (
            ":warning: *{project_name}* has exceeded budget "
            "({budget_percent}% consumed)\nBudget: ${budget_consumed} / ${budget_total}"
        )

    context = {
        "project_name": project.name,
        "budget_percent": f"{budget_percent:.0f}",
        "budget_consumed": f"{cost_to_date:,.0f}",
        "budget_total": f"{budget_total:,.0f}",
    }

    message = AlertService.render_template(template, context)

    return await _send_and_log_alert(
        db,
        project,
        alert_def,
        bot_token,
        leadership_channel_id,
        message,
        metadata={"budget_percent": float(budget_percent)},
    )


def _calculate_velocity_per_week(metrics: MetricsDB) -> float:
    """Calculate weekly velocity from metrics.

    Args:
        metrics: Metrics containing task completion data

    Returns:
        Velocity per week (tasks completed per week)
    """
    tasks_completed = metrics.tasks_completed or 0
    if tasks_completed <= 0:
        return 0.0

    if metrics.period_end and metrics.period_start:
        period_days = (metrics.period_end - metrics.period_start).days
        if period_days > 0:
            velocity_per_day = tasks_completed / period_days
            return velocity_per_day * DAYS_PER_WEEK

    return tasks_completed / DEFAULT_WEEKS_FOR_VELOCITY


def _is_timeline_at_risk(
    end_date: date,
    remaining_issues: int,
    velocity_per_week: float,
) -> bool:
    """Determine if the timeline is at risk based on velocity.

    Args:
        end_date: Project end date
        remaining_issues: Number of remaining issues
        velocity_per_week: Weekly velocity

    Returns:
        True if timeline is at risk, False otherwise
    """
    today = date.today()
    if end_date <= today:
        return False

    if remaining_issues <= 0 or velocity_per_week <= 0:
        return False

    weeks_remaining = max(1, (end_date - today).days / DAYS_PER_WEEK)
    weeks_needed = remaining_issues / velocity_per_week

    return weeks_needed > weeks_remaining


async def _check_timeline_at_risk(
    db: AsyncSession,
    project: ProjectDB,
    metrics: MetricsDB | None,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    leadership_channel_id: str,
) -> bool:
    """Check if project timeline is at risk based on velocity.

    Timeline is at risk when:
    - Project has an end_date
    - Current velocity suggests remaining work won't complete by end_date

    Args:
        db: Database session
        project: Project to check
        metrics: Latest metrics for the project
        alert_def: Alert definition for timeline at risk
        bot_token: Slack bot token
        leadership_channel_id: Leadership channel ID

    Returns:
        True if alert was sent, False otherwise
    """
    if not project.end_date or not metrics:
        return False

    remaining_issues = metrics.bugs_total or 0
    velocity_per_week = _calculate_velocity_per_week(metrics)

    if not _is_timeline_at_risk(project.end_date, remaining_issues, velocity_per_week):
        return False

    is_silenced = await AlertService.is_silenced(db, project.id, alert_def.id)
    if is_silenced:
        logger.debug(f"Skipping silenced project for timeline alert: {project.name}")
        return False

    was_notified = await AlertService.was_notified_this_month(
        db, project.id, alert_def.id
    )
    if was_notified:
        logger.debug(f"Already notified this month for timeline alert: {project.name}")
        return False

    today = date.today()
    weeks_remaining = max(1, (project.end_date - today).days / DAYS_PER_WEEK)

    template = await AlertService.get_template(db, alert_def.id, "initial")
    if not template:
        template = (
            ":warning: *{project_name}* timeline at risk\n"
            "{remaining_issues} issues remaining | {weeks_remaining} weeks left | "
            "Velocity: {velocity}/week"
        )

    context = {
        "project_name": project.name,
        "remaining_issues": remaining_issues,
        "weeks_remaining": f"{weeks_remaining:.1f}",
        "velocity": f"{velocity_per_week:.1f}",
    }

    message = AlertService.render_template(template, context)

    return await _send_and_log_alert(
        db,
        project,
        alert_def,
        bot_token,
        leadership_channel_id,
        message,
        metadata={
            "remaining_issues": remaining_issues,
            "weeks_remaining": weeks_remaining,
            "velocity_per_week": velocity_per_week,
        },
    )


async def _check_project_overdue(
    db: AsyncSession,
    project: ProjectDB,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    leadership_channel_id: str,
) -> bool:
    """Check if project is overdue (>grace_days past end_date).

    Args:
        db: Database session
        project: Project to check
        alert_def: Alert definition for project overdue
        bot_token: Slack bot token
        leadership_channel_id: Leadership channel ID

    Returns:
        True if alert was sent, False otherwise
    """
    if not project.end_date:
        return False

    today = date.today()
    days_past_end = (today - project.end_date).days

    grace_days = alert_def.config_json.get("grace_days", DEFAULT_GRACE_DAYS)

    if days_past_end <= grace_days:
        return False

    is_silenced = await AlertService.is_silenced(db, project.id, alert_def.id)
    if is_silenced:
        logger.debug(f"Skipping silenced project for overdue alert: {project.name}")
        return False

    was_notified = await AlertService.was_notified_this_month(
        db, project.id, alert_def.id
    )
    if was_notified:
        logger.debug(f"Already notified this month for overdue alert: {project.name}")
        return False

    template = await AlertService.get_template(db, alert_def.id, "initial")
    if not template:
        template = (
            ":rotating_light: *{project_name}* is {days_overdue} days past "
            "planned end date\nPlanned end: {end_date}"
        )

    context = {
        "project_name": project.name,
        "days_overdue": days_past_end,
        "end_date": project.end_date.strftime("%Y-%m-%d"),
    }

    message = AlertService.render_template(template, context)

    return await _send_and_log_alert(
        db,
        project,
        alert_def,
        bot_token,
        leadership_channel_id,
        message,
        metadata={"days_overdue": days_past_end},
    )


async def _send_and_log_alert(
    db: AsyncSession,
    project: ProjectDB,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    channel_id: str,
    message: str,
    metadata: dict | None = None,
) -> bool:
    """Send Slack message and log the notification.

    Args:
        db: Database session
        project: Project the alert is for
        alert_def: Alert definition
        bot_token: Slack bot token
        channel_id: Slack channel ID
        message: Message to send
        metadata: Optional metadata to log

    Returns:
        True if message was sent successfully, False otherwise
    """
    response = await SlackService.send_message(bot_token, channel_id, message)

    status = "sent" if response.get("ok") else "failed"
    error_message = response.get("error") if not response.get("ok") else None

    await AlertService.log_notification(
        db=db,
        project_id=project.id,
        alert_definition_id=alert_def.id,
        channel_id=channel_id,
        message=message,
        status=status,
        error_message=error_message,
        metadata=metadata,
    )

    if response.get("ok"):
        logger.info(f"Sent {alert_def.name} alert for project: {project.name}")
        return True

    logger.error(
        f"Failed to send {alert_def.name} alert for project {project.name}: "
        f"{error_message}"
    )
    return False
