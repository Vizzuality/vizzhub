"""Daily devstack source refresh — cron task. Refreshes GitHub SHAs + npm versions."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.services.sha_refresh import refresh_all_sources_tracked

logger = structlog.get_logger()

JOB_NAME = "refresh_devstack_sources"


async def refresh_devstack_sources(ctx: dict) -> dict:
    """Refresh GitHub SHAs and npm latest versions. Daily at 6 AM UTC."""
    logger.info("job_started", job_name=JOB_NAME)
    db: AsyncSession = ctx["db"]
    try:
        result = await refresh_all_sources_tracked(db)
    except Exception:
        logger.exception("job_failed", job_name=JOB_NAME)
        raise
    logger.info(
        "job_completed",
        job_name=JOB_NAME,
        refreshed=result.get("refreshed") if isinstance(result, dict) else None,
        failed=result.get("failed") if isinstance(result, dict) else None,
    )
    return result
