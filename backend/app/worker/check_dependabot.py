"""Dependabot alerts check job.

This cron job runs daily to check all active projects for new Dependabot
alerts and sends Slack notifications for high/critical severity vulnerabilities.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.project import ProjectDB
from app.models.slack import (
    AlertDefinitionDB,
    DependabotAlertTrackedDB,
    ScheduledJobRunDB,
)
from app.services.alert_service import AlertService
from app.services.collectors.dependabot import DependabotCollector
from app.services.slack_service import SlackService
from app.utils.slack import get_slack_bot_token
from app.worker.utils import complete_with_error

logger = logging.getLogger(__name__)

ALERT_NAME = "dependabot_high_critical"
NO_CVE = "No CVE"

# Reminder intervals by severity
REMINDER_DAYS = {
    "critical": 2,
    "high": 7,
}


async def check_dependabot_alerts(ctx: dict) -> dict[str, Any]:
    """Check all projects for new Dependabot alerts and send notifications.

    This job:
    1. Gets all active projects with GitHub repos and Slack channels configured
    2. For each project, fetches current Dependabot alerts from GitHub
    3. Compares against tracked alerts to find new ones
    4. Sends notifications for new alerts
    5. Marks resolved alerts when they disappear from GitHub

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
        job_name="check_dependabot_alerts",
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

        settings = get_settings()
        if not settings.github_token:
            return await complete_with_error(db, job_run, "GitHub token not configured")

        alert_definition = await _get_alert_definition(db)
        if not alert_definition:
            return await complete_with_error(
                db, job_run, f"Alert definition '{ALERT_NAME}' not found"
            )

        projects = await _get_eligible_projects(db)
        logger.info(f"Found {len(projects)} eligible projects to check")

        projects_checked = 0
        alerts_sent = 0

        for project in projects:
            try:
                is_silenced = await AlertService.is_silenced(
                    db, project.id, alert_definition.id
                )
                if is_silenced:
                    logger.debug(f"Skipping silenced project: {project.name}")
                    continue

                sent = await _process_project(
                    db,
                    project,
                    alert_definition,
                    bot_token,
                    settings.github_token,
                )
                projects_checked += 1
                alerts_sent += sent

            except Exception as e:
                logger.error(f"Error processing project {project.name}: {e}")
                continue

        job_run.status = "completed"
        job_run.projects_checked = projects_checked
        job_run.alerts_sent = alerts_sent
        job_run.completed_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            f"Dependabot check completed: {projects_checked} projects checked, "
            f"{alerts_sent} alerts sent"
        )

        return {
            "status": "completed",
            "job_run_id": job_run.id,
            "projects_checked": projects_checked,
            "alerts_sent": alerts_sent,
        }

    except Exception as e:
        logger.exception("Dependabot check job failed")
        return await complete_with_error(db, job_run, str(e))


async def _get_alert_definition(db: AsyncSession) -> AlertDefinitionDB | None:
    """Get the dependabot alert definition."""
    result = await db.execute(
        select(AlertDefinitionDB).where(
            AlertDefinitionDB.name == ALERT_NAME,
            AlertDefinitionDB.is_enabled.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _get_eligible_projects(db: AsyncSession) -> list[ProjectDB]:
    """Get all active projects with GitHub repos and Slack channels."""
    result = await db.execute(
        select(ProjectDB).where(
            ProjectDB.github_repo.isnot(None),
            ProjectDB.slack_channel_id.isnot(None),
            ProjectDB.status == "in_progress",
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
    """Process a single project for Dependabot alerts.

    Args:
        db: Database session
        project: Project to check
        alert_definition: Alert definition for notifications
        bot_token: Slack bot token
        github_token: GitHub API token

    Returns:
        Number of alerts sent for this project
    """
    alerts_sent = 0

    current_alerts = await DependabotCollector.fetch_alerts(
        project.github_repo, github_token
    )

    current_alert_ids = {alert["number"] for alert in current_alerts}

    tracked_alerts = await _get_tracked_alerts(db, project.id)
    tracked_alert_ids = {
        ta.github_alert_id for ta in tracked_alerts if not ta.resolved_at
    }

    new_alert_ids = current_alert_ids - tracked_alert_ids

    # Backfill manifest_path for tracked alerts missing it
    await _backfill_manifest_paths(db, tracked_alerts, current_alerts)

    for alert in current_alerts:
        if alert["number"] in new_alert_ids:
            sent = await _notify_new_alert(
                db, project, alert_definition, bot_token, alert
            )
            if sent:
                alerts_sent += 1

    # Send reminders for unresolved alerts that need them
    alerts_sent += await _send_reminders(
        db, project, alert_definition, bot_token, tracked_alerts, current_alerts
    )

    resolved_ids = tracked_alert_ids - current_alert_ids
    if resolved_ids:
        await _mark_alerts_resolved(db, project.id, resolved_ids)

    return alerts_sent


async def _backfill_manifest_paths(
    db: AsyncSession,
    tracked_alerts: list[DependabotAlertTrackedDB],
    current_alerts: list[dict],
) -> None:
    """Fill manifest_path for tracked alerts that are missing it."""
    alerts_by_id = {alert["number"]: alert for alert in current_alerts}
    updated = False

    for tracked in tracked_alerts:
        if tracked.manifest_path or tracked.resolved_at:
            continue
        current = alerts_by_id.get(tracked.github_alert_id)
        if not current:
            continue
        manifest = current.get("dependency", {}).get("manifest_path")
        if manifest:
            tracked.manifest_path = manifest
            updated = True

    if updated:
        await db.commit()


async def _get_tracked_alerts(
    db: AsyncSession, project_id
) -> list[DependabotAlertTrackedDB]:
    """Get all tracked alerts for a project."""
    result = await db.execute(
        select(DependabotAlertTrackedDB).where(
            DependabotAlertTrackedDB.project_id == project_id
        )
    )
    return list(result.scalars().all())


async def _notify_new_alert(
    db: AsyncSession,
    project: ProjectDB,
    alert_definition: AlertDefinitionDB,
    bot_token: str,
    alert: dict,
) -> bool:
    """Send notification for a new Dependabot alert and track it.

    Args:
        db: Database session
        project: Project with the alert
        alert_definition: Alert definition for templates
        bot_token: Slack bot token
        alert: Alert data from GitHub

    Returns:
        True if notification was sent successfully
    """
    alert_info = DependabotCollector.extract_alert_info(alert)

    template = await AlertService.get_template(db, alert_definition.id, "initial")
    if not template:
        template = (
            ":warning: New Dependabot alert in *{project_name}*: "
            "{package_name} ({severity}) - {cve_id}\n"
            "Module: {manifest_path}\n<{alert_url}|View in GitHub>"
        )

    severity = alert_info["severity"] or "Unknown"
    package_name = alert_info["package_name"] or "Unknown package"
    cve_id = alert_info["cve_id"] or NO_CVE
    manifest_path = alert_info.get("manifest_path") or ""
    alert_id = alert_info["github_alert_id"]
    alert_url = (
        f"https://github.com/{project.github_repo}/security/dependabot/{alert_id}"
    )

    context = {
        "project_name": project.name,
        "package_name": package_name,
        "severity": severity,
        "cve_id": cve_id,
        "manifest_path": manifest_path,
        "github_alert_id": alert_id,
        "alert_url": alert_url,
        # Aliases for template compatibility
        "vuln_severity": severity,
        "vuln_package": package_name,
        "vuln_cve": cve_id,
        "vuln_url": alert_url,
    }

    message = AlertService.render_template(template, context)

    response = await SlackService.send_message(
        bot_token, project.slack_channel_id, message
    )

    status = "sent" if response.get("ok") else "failed"
    error_message = response.get("error") if not response.get("ok") else None

    await AlertService.log_notification(
        db=db,
        project_id=project.id,
        alert_definition_id=alert_definition.id,
        channel_id=project.slack_channel_id,
        message=message,
        status=status,
        error_message=error_message,
        metadata={
            "github_alert_id": alert_info["github_alert_id"],
            "package_name": alert_info["package_name"],
            "severity": alert_info["severity"],
        },
    )

    if response.get("ok"):
        tracked = DependabotAlertTrackedDB(
            project_id=project.id,
            github_alert_id=alert_info["github_alert_id"],
            package_name=alert_info["package_name"],
            severity=alert_info["severity"],
            cve_id=alert_info["cve_id"],
            manifest_path=alert_info.get("manifest_path"),
            last_notified_at=datetime.now(timezone.utc),
        )
        db.add(tracked)
        await db.commit()
        return True

    return False


def _is_reminder_due(
    tracked: DependabotAlertTrackedDB,
    current_alert_ids: set[int],
    now: datetime,
) -> bool:
    """Check if a tracked alert needs a reminder notification."""
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


def _build_reminder_context(
    project: ProjectDB,
    tracked: DependabotAlertTrackedDB,
    now: datetime,
) -> dict:
    """Build template context for a reminder notification."""
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


async def _send_reminders(
    db: AsyncSession,
    project: ProjectDB,
    alert_definition: AlertDefinitionDB,
    bot_token: str,
    tracked_alerts: list[DependabotAlertTrackedDB],
    current_alerts: list[dict],
) -> int:
    """Send reminders for unresolved alerts based on severity.

    Critical: reminder every 2 days
    High: reminder every 7 days
    """
    now = datetime.now(timezone.utc)
    reminders_sent = 0
    current_alert_ids = {alert["number"] for alert in current_alerts}

    template = await AlertService.get_template(db, alert_definition.id, "reminder")
    if not template:
        template = (
            ":alarm_clock: Reminder: *{project_name}* has unresolved {severity} vulnerability\n"
            "Package: {package_name} (open for {days_open} days)\n"
            "Module: {manifest_path}\n<{alert_url}|View in GitHub>"
        )

    for tracked in tracked_alerts:
        if not _is_reminder_due(tracked, current_alert_ids, now):
            continue

        context = _build_reminder_context(project, tracked, now)
        message = AlertService.render_template(template, context)

        response = await SlackService.send_message(
            bot_token, project.slack_channel_id, message
        )

        if response.get("ok"):
            tracked.last_notified_at = now
            await db.commit()
            reminders_sent += 1
            logger.info(
                f"Sent reminder for {tracked.severity} alert #{tracked.github_alert_id} "
                f"in {project.name} (open {context['days_open']} days)"
            )

    return reminders_sent


async def _mark_alerts_resolved(
    db: AsyncSession, project_id, resolved_ids: set[int]
) -> None:
    """Mark tracked alerts as resolved when they disappear from GitHub."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(DependabotAlertTrackedDB).where(
            DependabotAlertTrackedDB.project_id == project_id,
            DependabotAlertTrackedDB.github_alert_id.in_(resolved_ids),
            DependabotAlertTrackedDB.resolved_at.is_(None),
        )
    )
    tracked_alerts = result.scalars().all()

    for tracked in tracked_alerts:
        tracked.resolved_at = now

    await db.commit()
