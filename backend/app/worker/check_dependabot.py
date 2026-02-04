"""Dependabot alerts check job.

This cron job runs daily to check all active projects for new Dependabot
alerts and sends Slack notifications for high/critical severity vulnerabilities.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.project import ProjectDB
from app.models.slack import (
    AlertDefinitionDB,
    DependabotAlertTrackedDB,
    ScheduledJobRunDB,
    SlackConfigDB,
)
from app.services.alert_service import AlertService
from app.services.collectors.dependabot import DependabotCollector
from app.services.slack_service import SlackService

logger = logging.getLogger(__name__)

ALERT_NAME = "dependabot_high_critical"


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
        slack_config = await _get_slack_config(db)
        if not slack_config or not slack_config.bot_token_encrypted:
            return await _complete_with_error(
                db, job_run, "Slack not configured - missing bot token"
            )

        settings = get_settings()
        if not settings.github_token:
            return await _complete_with_error(
                db, job_run, "GitHub token not configured"
            )

        alert_definition = await _get_alert_definition(db)
        if not alert_definition:
            return await _complete_with_error(
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
                    slack_config.bot_token_encrypted,
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
        return await _complete_with_error(db, job_run, str(e))


async def _get_slack_config(db: AsyncSession) -> SlackConfigDB | None:
    """Get the global Slack configuration."""
    result = await db.execute(select(SlackConfigDB).limit(1))
    return result.scalar_one_or_none()


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

    for alert in current_alerts:
        if alert["number"] in new_alert_ids:
            sent = await _notify_new_alert(
                db, project, alert_definition, bot_token, alert
            )
            if sent:
                alerts_sent += 1

    resolved_ids = tracked_alert_ids - current_alert_ids
    if resolved_ids:
        await _mark_alerts_resolved(db, project.id, resolved_ids)

    return alerts_sent


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
            "{package_name} ({severity}) - {cve_id}"
        )

    severity = alert_info["severity"] or "Unknown"
    package_name = alert_info["package_name"] or "Unknown package"
    cve_id = alert_info["cve_id"] or "No CVE"

    context = {
        "project_name": project.name,
        "package_name": package_name,
        "severity": severity,
        "cve_id": cve_id,
        "github_alert_id": alert_info["github_alert_id"],
        # Aliases for template compatibility
        "vuln_severity": severity,
        "vuln_package": package_name,
        "vuln_cve": cve_id,
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
            last_notified_at=datetime.now(timezone.utc),
        )
        db.add(tracked)
        await db.commit()
        return True

    return False


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


async def _complete_with_error(
    db: AsyncSession, job_run: ScheduledJobRunDB, error_message: str
) -> dict[str, Any]:
    """Complete the job run with an error status."""
    job_run.status = "error"
    job_run.error_message = error_message
    job_run.completed_at = datetime.now(timezone.utc)
    await db.commit()

    logger.error(f"Dependabot check job failed: {error_message}")

    return {
        "status": "error",
        "job_run_id": job_run.id,
        "projects_checked": 0,
        "alerts_sent": 0,
        "error": error_message,
    }
