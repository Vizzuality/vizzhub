"""Reporting period rotation scheduled job.

Runs on the 15th of each month at 00:00 UTC.
Finishes the currently active reporting period and creates + activates
a new one for the current month.
"""

import structlog
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models.slack import ScheduledJobRunDB
from app.modules.tracker.models.reporting_period import (
    ReportingPeriodDB,
    ReportingPeriodStatus,
)
from app.modules.tracker.schemas.reporting_period import ReportingPeriodCreate
from app.modules.tracker.services.period_service import (
    activate_period,
    create_period,
    finish_period,
    get_active_period,
)
from app.worker.utils import complete_with_error

logger = structlog.get_logger()


async def rotate_reporting_period(ctx: dict) -> dict[str, Any]:
    """Finish the active period and create + activate a new one for the current month.

    Runs on the 15th of each month. Handles edge cases:
    - No active period: creates and activates new one without error
    - Period for current month already exists: activates it instead of creating
    """
    today = date.today()
    if today.day != 15:
        return {"status": "skipped", "alerts_sent": 0}

    db: AsyncSession = ctx["db"]

    job_run = ScheduledJobRunDB(
        job_name="rotate_reporting_period",
        status="running",
        projects_checked=0,
        alerts_sent=0,
    )
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    try:
        active = await get_active_period(db)
        if active:
            await finish_period(active.id, db)
            await db.commit()
            logger.info("period_finished", period_date=str(active.date))

        new_date = today.replace(day=1)

        existing = await db.execute(
            select(ReportingPeriodDB).where(
                ReportingPeriodDB.date == new_date
            )
        )
        existing_period = existing.scalar_one_or_none()

        if existing_period:
            if existing_period.status != ReportingPeriodStatus.ACTIVE.value:
                await activate_period(existing_period.id, db)
                await db.commit()
                logger.info("period_activated", period_date=str(new_date))
        else:
            data = ReportingPeriodCreate(date=today)
            new_period = await create_period(data, db)
            await activate_period(new_period.id, db)
            await db.commit()
            logger.info("period_created_and_activated", period_date=str(new_date))

        job_run.status = "completed"
        job_run.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return {
            "status": "completed",
            "job_run_id": job_run.id,
            "alerts_sent": 0,
        }

    except Exception as e:
        logger.exception("job_failed")
        return await complete_with_error(db, job_run, str(e))
