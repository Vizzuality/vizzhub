"""Refresh GitHub SHAs for all active devstack catalog entries."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.services.github_sha import fetch_github_sha
from app.modules.notifications.public import ScheduledJobRunDB

logger = structlog.get_logger()

JOB_NAME = "refresh_devstack_shas"


async def refresh_all_shas(db: AsyncSession) -> dict[str, int]:
    """Refresh github_sha for all active github entries.

    Returns: {total, updated, unchanged, failed}.
    """
    result = await db.execute(
        select(DevstackEntryDB).where(
            DevstackEntryDB.active.is_(True),
            DevstackEntryDB.install_method == "github",
            DevstackEntryDB.url.isnot(None),
        )
    )
    entries = result.scalars().all()
    token = await IntegrationTokenService.get_token(db, "github")

    updated = unchanged = failed = 0
    for entry in entries:
        new_sha = await fetch_github_sha(entry.url, token)
        if new_sha is None:
            failed += 1
        elif new_sha != entry.github_sha:
            entry.github_sha = new_sha
            updated += 1
        else:
            unchanged += 1

    if updated > 0:
        await db.commit()

    summary = {"total": len(entries), "updated": updated, "unchanged": unchanged, "failed": failed}
    logger.info("devstack_sha_refresh_completed", **summary)
    return summary


async def refresh_all_shas_tracked(db: AsyncSession) -> dict[str, int]:
    """Run refresh_all_shas and record the run in ScheduledJobRunDB.

    Used by both the cron task and the manual admin endpoint so the run
    shows up in admin > scheduled jobs.
    """
    job_run = ScheduledJobRunDB(job_name=JOB_NAME, status="running")
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    try:
        result = await refresh_all_shas(db)
        job_run.status = "completed"
        job_run.completed_at = datetime.now(timezone.utc)
        job_run.projects_checked = result["total"]
        job_run.alerts_sent = result["updated"]
        await db.commit()
        return result
    except Exception as e:
        job_run.status = "error"
        job_run.completed_at = datetime.now(timezone.utc)
        job_run.error_message = str(e)
        await db.commit()
        raise
