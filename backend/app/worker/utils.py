"""Shared utilities for worker modules."""

import structlog
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models.slack import ScheduledJobRunDB

logger = structlog.get_logger()


async def start_job_run(db: AsyncSession, job_name: str) -> ScheduledJobRunDB:
    """Persist a fresh ``running`` ScheduledJobRunDB row and return it.

    Counts default to zero so callers can incrementally bump them as work
    happens; the row is committed + refreshed so the auto-generated id is
    available before the body runs.
    """
    job_run = ScheduledJobRunDB(
        job_name=job_name,
        status="running",
        projects_checked=0,
        alerts_sent=0,
    )
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)
    return job_run


async def complete_job_run(db: AsyncSession, job_run: ScheduledJobRunDB) -> None:
    """Mark ``job_run`` as completed (success) and commit.

    The caller is expected to have set any job-specific counters
    (alerts_sent, projects_checked) on ``job_run`` before calling.
    """
    job_run.status = "completed"
    job_run.completed_at = datetime.now(timezone.utc)
    await db.commit()


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
