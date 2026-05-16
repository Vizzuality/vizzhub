"""Dependabot reminder cadence: re-notify unresolved high/critical alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import (
    AlertDefinitionDB,
    DependabotAlertTrackedDB,
)
from app.modules.notifications.services.alert_service import AlertService
from app.worker.dependabot.shared import NO_CVE, REMINDER_DAYS, slack_send

logger = structlog.get_logger()


def is_reminder_due(
    tracked: DependabotAlertTrackedDB,
    current_alert_ids: set[int],
    now: datetime,
) -> bool:
    """True iff this tracked alert is unresolved, still open in GitHub, and past its cadence."""
    if tracked.resolved_at:
        return False
    if tracked.github_alert_id not in current_alert_ids:
        return False

    severity = (tracked.severity or "").lower()
    reminder_days = REMINDER_DAYS.get(severity)
    if not reminder_days:
        return False

    if tracked.last_notified_at:
        next_reminder = tracked.last_notified_at + timedelta(days=reminder_days)
        if now < next_reminder:
            return False

    return True


def build_reminder_context(
    project: ProjectDB,
    tracked: DependabotAlertTrackedDB,
    now: datetime,
) -> dict:
    """Template context for a reminder notification."""
    days_open = (now - tracked.first_seen_at).days if tracked.first_seen_at else 0
    alert_url = (
        f"https://github.com/{project.github_repo}"
        f"/security/dependabot/{tracked.github_alert_id}"
    )
    return {
        "project_name": project.name,
        "package_name": tracked.package_name or "Unknown",
        "severity": tracked.severity or "Unknown",
        "cve_id": tracked.cve_id or NO_CVE,
        "manifest_path": tracked.manifest_path or "",
        "days_open": days_open,
        "alert_url": alert_url,
        "vuln_severity": tracked.severity or "Unknown",
        "vuln_package": tracked.package_name or "Unknown",
        "vuln_cve": tracked.cve_id or NO_CVE,
        "vuln_url": alert_url,
        "vuln_age_days": days_open,
    }


async def send_reminders(
    db: AsyncSession,
    project: ProjectDB,
    alert_definition: AlertDefinitionDB,
    bot_token: str,
    tracked_alerts: list[DependabotAlertTrackedDB],
    current_alerts: list[dict],
) -> int:
    """Send reminders for unresolved alerts whose cadence has elapsed."""
    now = datetime.now(timezone.utc)
    reminders_sent = 0
    current_alert_ids = {alert["number"] for alert in current_alerts}

    template = await AlertService.get_template(db, alert_definition.id, "reminder") or (
        ":alarm_clock: Reminder: *{project_name}* has unresolved {severity} vulnerability\n"
        "Package: {package_name} (open for {days_open} days)\n"
        "Module: {manifest_path}\n<{alert_url}|View in GitHub>"
    )

    for tracked in tracked_alerts:
        if not is_reminder_due(tracked, current_alert_ids, now):
            continue

        context = build_reminder_context(project, tracked, now)
        message = AlertService.render_template(template, context)
        response = await slack_send(bot_token, project.slack_channel_id, message)

        if response.get("ok"):
            tracked.last_notified_at = now
            await db.commit()
            reminders_sent += 1
            logger.info(
                "reminder_sent",
                severity=tracked.severity,
                alert_id=tracked.github_alert_id,
                project=project.name,
                days_open=context["days_open"],
            )

    return reminders_sent
