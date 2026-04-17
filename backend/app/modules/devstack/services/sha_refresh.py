"""Refresh GitHub SHAs for all active devstack catalog entries."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.services.github_sha import fetch_github_sha

logger = structlog.get_logger()


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
