"""Dependabot alert tracking: query existing rows, backfill, notify, resolve."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.notifications.models.slack import (
    AlertDefinitionDB,
    DependabotAlertTrackedDB,
)
from app.modules.notifications.services.alert_service import AlertService
from app.modules.scorecard.services.collectors.dependabot import DependabotCollector
from app.worker.dependabot.shared import NO_CVE, slack_send

logger = structlog.get_logger()


async def get_tracked_alerts(
    db: AsyncSession, project_id: UUID
) -> list[DependabotAlertTrackedDB]:
    """All tracked alert rows for a project (resolved + unresolved)."""
    result = await db.execute(
        select(DependabotAlertTrackedDB).where(
            DependabotAlertTrackedDB.project_id == project_id
        )
    )
    return list(result.scalars().all())


async def backfill_manifest_paths(
    db: AsyncSession,
    tracked_alerts: list[DependabotAlertTrackedDB],
    current_alerts: list[dict],
) -> None:
    """Fill `manifest_path` on tracked rows that pre-date the column."""
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


async def notify_new_alert(
    db: AsyncSession,
    project: ProjectDB,
    alert_definition: AlertDefinitionDB,
    bot_token: str,
    alert: dict,
) -> bool:
    """Send Slack notification for a new alert + persist a tracking row."""
    alert_info = DependabotCollector.extract_alert_info(alert)

    template = await AlertService.get_template(db, alert_definition.id, "initial") or (
        ":warning: New Dependabot alert in *{project_name}*: "
        "{package_name} ({severity}) - {cve_id}\n"
        "Module: {manifest_path}\n<{alert_url}|View in GitHub>"
    )

    severity = alert_info["severity"] or "Unknown"
    package_name = alert_info["package_name"] or "Unknown package"
    cve_id = alert_info["cve_id"] or NO_CVE
    manifest_path = alert_info.get("manifest_path") or ""
    alert_id = alert_info["github_alert_id"]
    alert_url = f"https://github.com/{project.github_repo}/security/dependabot/{alert_id}"

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
    response = await slack_send(bot_token, project.slack_channel_id, message)

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


async def mark_alerts_resolved(
    db: AsyncSession, project_id: UUID, resolved_ids: set[int]
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
    for tracked in result.scalars().all():
        tracked.resolved_at = now

    await db.commit()
