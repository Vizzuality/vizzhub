"""Budget-exceeded alert: project has consumed ≥100% of its budget."""

from __future__ import annotations

from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import AlertDefinitionDB
from app.modules.notifications.services.alert_service import AlertService
from app.modules.scorecard.models.metrics import MetricsDB
from app.worker.business_alerts.shared import send_and_log_alert

logger = structlog.get_logger()


async def check_budget_exceeded(
    db: AsyncSession,
    project: ProjectDB,
    metrics: MetricsDB | None,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    leadership_channel_id: str,
) -> bool:
    """Send a Slack alert when consumed/total ≥ 100%; return True if sent."""
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

    if await AlertService.is_silenced(db, project.id, alert_def.id):
        logger.debug("alert_silenced", alert_type="budget_exceeded", project=project.name)
        return False
    if await AlertService.was_notified_this_month(db, project.id, alert_def.id):
        logger.debug("alert_already_notified", alert_type="budget_exceeded", project=project.name)
        return False

    template = await AlertService.get_template(db, alert_def.id, "initial") or (
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

    return await send_and_log_alert(
        db,
        project,
        alert_def,
        bot_token,
        leadership_channel_id,
        message,
        metadata={"budget_percent": float(budget_percent)},
    )
