"""Dependabot alert tracking: query existing rows, backfill, resolve."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models.slack import DependabotAlertTrackedDB

logger = structlog.get_logger()


async def get_tracked_alerts(db: AsyncSession, project_id: UUID) -> list[DependabotAlertTrackedDB]:
    """All tracked alert rows for a project (resolved + unresolved)."""
    result = await db.execute(
        select(DependabotAlertTrackedDB).where(DependabotAlertTrackedDB.project_id == project_id)
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


async def mark_alerts_resolved(db: AsyncSession, project_id: UUID, resolved_ids: set[int]) -> None:
    """Mark tracked alerts as resolved when they disappear from GitHub."""
    now = datetime.now(UTC)

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
