"""Refresh catalog entry metadata (GitHub SHAs + npm versions)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.services.github_sha import fetch_github_sha
from app.modules.devstack.services.npm_security import fetch_npm_advisories
from app.modules.devstack.services.npm_version import (
    fetch_npm_latest_version,  # kept for backward compat
    fetch_npm_package_info,
)
from app.modules.notifications.public import ScheduledJobRunDB

logger = structlog.get_logger()

JOB_NAME = "refresh_devstack_sources"


async def _refresh_github_entry(
    entry: DevstackEntryDB, github_token: str | None
) -> str:
    """Return 'updated' | 'unchanged' | 'failed' for one github entry."""
    new_sha = await fetch_github_sha(entry.url, github_token)
    if new_sha is None:
        return "failed"
    if new_sha != entry.github_sha:
        entry.github_sha = new_sha
        return "updated"
    return "unchanged"


def _apply_npm_deprecation(entry: DevstackEntryDB, info: dict) -> bool:
    """Sync version + deprecation from npm info. Return True if anything changed."""
    changed = False
    if info["version"] != entry.latest_package_version:
        entry.latest_package_version = info["version"]
        changed = True
    new_message = info["deprecation_message"]
    new_deprecated = new_message is not None
    if (
        new_deprecated != entry.deprecated
        or new_message != entry.deprecation_message
    ):
        entry.deprecated = new_deprecated
        entry.deprecation_message = new_message
        changed = True
    return changed


async def _refresh_npm_advisories(
    entry: DevstackEntryDB, info: dict, github_token: str | None
) -> bool:
    """Fetch + persist advisories for one npm entry. Return True if payload changed."""
    version_to_check = entry.package_version or info["version"]
    advisories = await fetch_npm_advisories(
        entry.package, version_to_check, github_token
    )
    if advisories is None:
        return False
    entry.vulnerabilities_checked_at = datetime.now(timezone.utc)
    if advisories != entry.vulnerabilities:
        entry.vulnerabilities = advisories
        return True
    return False


async def _refresh_npm_entry(
    entry: DevstackEntryDB, github_token: str | None
) -> str:
    """Return 'updated' | 'unchanged' | 'failed' for one npm entry."""
    info = await fetch_npm_package_info(entry.package)
    if info is None:
        return "failed"
    changed = _apply_npm_deprecation(entry, info)
    if await _refresh_npm_advisories(entry, info, github_token):
        changed = True
    return "updated" if changed else "unchanged"


async def refresh_all_sources(db: AsyncSession) -> dict[str, int]:
    """Refresh github_sha and latest_package_version for all active entries.

    - github entries: refetch blob SHA
    - npm entries: refetch latest published version + deprecation + advisories
    - claude_plugin entries: skipped (no auto-tracking)

    Returns: {total, updated, unchanged, failed}.
    """
    result = await db.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.active.is_(True))
    )
    entries = result.scalars().all()
    github_token = await IntegrationTokenService.get_token(db, "github")

    counters: dict[str, int] = {"updated": 0, "unchanged": 0, "failed": 0}
    processed = 0

    for entry in entries:
        if entry.install_method == "github" and entry.url:
            processed += 1
            counters[await _refresh_github_entry(entry, github_token)] += 1
        elif entry.install_method == "npm" and entry.package:
            processed += 1
            counters[await _refresh_npm_entry(entry, github_token)] += 1
        # claude_plugin: skipped

    if counters["updated"] > 0:
        await db.commit()

    summary = {"total": processed, **counters}
    logger.info("devstack_sources_refresh_completed", **summary)
    return summary


async def refresh_all_sources_tracked(db: AsyncSession) -> dict[str, int]:
    """Run refresh_all_sources and record the run in ScheduledJobRunDB."""
    job_run = ScheduledJobRunDB(job_name=JOB_NAME, status="running")
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    try:
        result = await refresh_all_sources(db)
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
