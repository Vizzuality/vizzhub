"""Timeline-at-risk alert: velocity suggests remaining issues won't fit before end_date."""

from __future__ import annotations

from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import AlertDefinitionDB
from app.modules.notifications.services.alert_service import AlertService
from app.modules.scorecard.models.metrics import MetricsDB
from app.worker.business_alerts.shared import (
    DAYS_PER_WEEK,
    DEFAULT_WEEKS_FOR_VELOCITY,
    send_and_log_alert,
)

logger = structlog.get_logger()


def calculate_velocity_per_week(metrics: MetricsDB) -> float:
    """Weekly task velocity inferred from the latest metrics row."""
    tasks_completed = metrics.tasks_completed or 0
    if tasks_completed <= 0:
        return 0.0

    if metrics.period_end and metrics.period_start:
        period_days = (metrics.period_end - metrics.period_start).days
        if period_days > 0:
            velocity_per_day = tasks_completed / period_days
            return velocity_per_day * DAYS_PER_WEEK

    return tasks_completed / DEFAULT_WEEKS_FOR_VELOCITY


def is_timeline_at_risk(
    end_date: date,
    remaining_issues: int,
    velocity_per_week: float,
) -> bool:
    """True if `weeks_needed > weeks_remaining`."""
    today = date.today()
    if end_date <= today:
        return False
    if remaining_issues <= 0 or velocity_per_week <= 0:
        return False

    weeks_remaining = max(1, (end_date - today).days / DAYS_PER_WEEK)
    weeks_needed = remaining_issues / velocity_per_week
    return weeks_needed > weeks_remaining


async def check_timeline_at_risk(
    db: AsyncSession,
    project: ProjectDB,
    metrics: MetricsDB | None,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    leadership_channel_id: str,
) -> bool:
    """Send a Slack alert when remaining work won't fit before end_date."""
    if not project.end_date or not metrics:
        return False

    remaining_issues = metrics.bugs_total or 0
    velocity_per_week = calculate_velocity_per_week(metrics)
    if not is_timeline_at_risk(project.end_date, remaining_issues, velocity_per_week):
        return False

    if await AlertService.is_silenced(db, project.id, alert_def.id):
        logger.debug("alert_silenced", alert_type="timeline_at_risk", project=project.name)
        return False
    if await AlertService.was_notified_this_month(db, project.id, alert_def.id):
        logger.debug("alert_already_notified", alert_type="timeline_at_risk", project=project.name)
        return False

    today = date.today()
    weeks_remaining = max(1, (project.end_date - today).days / DAYS_PER_WEEK)

    template = await AlertService.get_template(db, alert_def.id, "initial") or (
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

    return await send_and_log_alert(
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
