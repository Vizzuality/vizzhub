"""Project-overdue alert: project is past end_date plus a grace period."""

from __future__ import annotations

from datetime import date

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import AlertDefinitionDB
from app.modules.notifications.services.alert_service import AlertService
from app.worker.business_alerts.shared import DEFAULT_GRACE_DAYS, send_and_log_alert

logger = structlog.get_logger()


async def check_project_overdue(
    db: AsyncSession,
    project: ProjectDB,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    leadership_channel_id: str,
) -> bool:
    """Send a Slack alert when project is more than `grace_days` past end_date."""
    if not project.end_date:
        return False

    today = date.today()
    days_past_end = (today - project.end_date).days
    grace_days = alert_def.config_json.get("grace_days", DEFAULT_GRACE_DAYS)
    if days_past_end <= grace_days:
        return False

    if await AlertService.is_silenced(db, project.id, alert_def.id):
        logger.debug("alert_silenced", alert_type="project_overdue", project=project.name)
        return False
    if await AlertService.was_notified_this_month(db, project.id, alert_def.id):
        logger.debug("alert_already_notified", alert_type="project_overdue", project=project.name)
        return False

    template = await AlertService.get_template(db, alert_def.id, "initial") or (
        ":rotating_light: *{project_name}* is {days_overdue} days past "
        "planned end date\nPlanned end: {end_date}"
    )
    context = {
        "project_name": project.name,
        "days_overdue": days_past_end,
        "end_date": project.end_date.strftime("%Y-%m-%d"),
    }
    message = AlertService.render_template(template, context)

    return await send_and_log_alert(
        db,
        project,
        alert_def,
        bot_token,
        leadership_channel_id,
        message,
        metadata={"days_overdue": days_past_end},
    )
