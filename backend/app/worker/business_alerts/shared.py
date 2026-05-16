"""Shared helpers for business-alert evaluators.

Centralises the I/O surface so test patches keep a single target
(`app.worker.business_alerts.shared.SlackService.send_message`).
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import AlertDefinitionDB
from app.modules.notifications.services.alert_service import AlertService
from app.modules.notifications.services.slack_service import SlackService
from app.modules.scorecard.models.metrics import MetricsDB, SnapshotType

logger = structlog.get_logger()

ALERT_NAMES = {
    "budget_exceeded": "budget_exceeded",
    "timeline_at_risk": "timeline_at_risk",
    "project_overdue": "project_overdue",
}

DEFAULT_GRACE_DAYS = 30
DAYS_PER_WEEK = 7
DEFAULT_WEEKS_FOR_VELOCITY = 4


async def get_latest_metrics(db: AsyncSession, project_id: UUID) -> MetricsDB | None:
    """Latest cumulative metrics for a project, or None."""
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


async def send_and_log_alert(
    db: AsyncSession,
    project: ProjectDB,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    channel_id: str,
    message: str,
    metadata: dict | None = None,
) -> bool:
    """Send a Slack message + log the notification; return True on success."""
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
        logger.info("alert_sent", alert_type=alert_def.name, project=project.name)
        return True

    logger.error(
        "alert_send_failed",
        alert_type=alert_def.name,
        project=project.name,
        error=error_message,
    )
    return False
