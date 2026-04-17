"""Daily devstack SHA refresh — cron task."""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.services.sha_refresh import refresh_all_shas

logger = structlog.get_logger()


async def refresh_devstack_shas(ctx: dict) -> dict[str, Any]:
    """Refresh GitHub SHAs for all active devstack entries. Daily at 6 AM UTC."""
    db: AsyncSession = ctx["db"]
    logger.info("devstack_sha_cron_started")
    try:
        result = await refresh_all_shas(db)
        logger.info("devstack_sha_cron_completed", **result)
        return {"status": "completed", **result}
    except Exception as e:
        logger.exception("devstack_sha_cron_failed")
        return {"status": "error", "error": str(e)}
