"""Daily ECB exchange rate fetch — cron task."""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.exchange_rate_service import fetch_and_store_rates
from app.modules.scorecard.models.slack import ScheduledJobRunDB

logger = logging.getLogger(__name__)

JOB_NAME = "fetch_exchange_rates"


async def fetch_exchange_rates(ctx: dict) -> dict[str, Any]:
    """Fetch and store ECB daily exchange rates.

    Scheduled daily at 14:30 UTC (ECB publishes ~14:00 UTC).
    """
    db: AsyncSession = ctx["db"]

    job_run = ScheduledJobRunDB(
        job_name=JOB_NAME,
        status="running",
        projects_checked=0,
        alerts_sent=0,
    )
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    try:
        result = await fetch_and_store_rates(db)
        job_run.status = "completed"
        job_run.completed_at = datetime.now(timezone.utc)
        job_run.projects_checked = result.get("currencies_stored", 0)
        await db.commit()
        logger.info("ECB rates fetched: %s", result)
        return {"status": "completed", "job_run_id": job_run.id, **result}
    except Exception as e:
        logger.exception("ECB rate fetch failed")
        job_run.status = "error"
        job_run.completed_at = datetime.now(timezone.utc)
        job_run.error_message = str(e)
        await db.commit()
        return {"status": "error", "job_run_id": job_run.id, "error": str(e)}
