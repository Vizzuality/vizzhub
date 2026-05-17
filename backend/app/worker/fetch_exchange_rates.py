"""Daily ECB exchange rate fetch — cron task."""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.exchange_rate_service import fetch_and_store_rates
from app.worker.utils import complete_job_run, complete_with_error, start_job_run

logger = structlog.get_logger()

JOB_NAME = "fetch_exchange_rates"


async def fetch_exchange_rates(ctx: dict) -> dict[str, Any]:
    """Fetch and store ECB daily exchange rates.

    Scheduled daily at 14:30 UTC (ECB publishes ~14:00 UTC).
    """
    db: AsyncSession = ctx["db"]
    job_run = await start_job_run(db, JOB_NAME)

    try:
        result = await fetch_and_store_rates(db)
        job_run.projects_checked = result.get("currencies_stored", 0)
        await complete_job_run(db, job_run)
        logger.info("rates_fetched", **result)
        return {"status": "completed", "job_run_id": job_run.id, **result}
    except Exception as e:
        logger.exception("job_failed")
        return await complete_with_error(db, job_run, str(e))
