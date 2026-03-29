"""Shared utilities for worker modules."""

import structlog
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models.slack import ScheduledJobRunDB

logger = structlog.get_logger()


async def complete_with_error(
    db: AsyncSession, job_run: ScheduledJobRunDB, error_message: str
) -> dict[str, Any]:
    """Complete a scheduled job run with an error status.

    Args:
        db: Database session
        job_run: The job run record to update
        error_message: Description of the error

    Returns:
        Dict with error status and job run details
    """
    job_run.status = "error"
    job_run.error_message = error_message
    job_run.completed_at = datetime.now(timezone.utc)
    await db.commit()

    logger.error("job_failed", job_name=job_run.job_name, error=error_message)

    return {
        "status": "error",
        "job_run_id": job_run.id,
        "projects_checked": 0,
        "alerts_sent": 0,
        "error": error_message,
    }
