"""Monthly scorecard capture cron job.

Runs on the 5th of each month at 2 AM UTC. Captures current month
metrics for all live projects with has_scorecard enabled.
"""

import asyncio
import structlog
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.scorecard.api.capture import (
    _build_metrics_data,
    _collect_from_github,
    _collect_from_jira,
    _first_day_of_month,
    _last_day_of_month,
)
from app.modules.scorecard.models.metrics import SnapshotType
from app.modules.notifications.models.slack import ScheduledJobRunDB
from app.modules.scorecard.services.metrics_service import MetricsService
from app.modules.tracker.public import inject_evm_into_preserved

logger = structlog.get_logger()


async def _get_scorecard_projects(db: AsyncSession) -> list[ProjectDB]:
    """Get all live projects with scorecard enabled."""
    result = await db.execute(
        select(ProjectDB).where(
            ProjectDB.status == "live",
            ProjectDB.has_scorecard.is_(True),
        )
    )
    return list(result.scalars().all())


async def monthly_scorecard_capture(ctx: dict) -> dict:
    """Capture current month metrics for all scorecard-enabled projects."""
    from app.config import get_scoring_config

    db: AsyncSession = ctx["db"]
    score_cache = ctx.get("score_cache")
    config = get_scoring_config()

    job_run = ScheduledJobRunDB(
        job_name="monthly_scorecard_capture",
        status="running",
        projects_checked=0,
        alerts_sent=0,
    )
    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)
    # Hold the PK as a plain int so the outer except can use it even after a
    # rollback expires the ORM instance.
    job_run_id = job_run.id

    try:
        today = date.today()
        year, month = today.year, today.month

        if today.day <= 5:
            month -= 1
            if month < 1:
                month = 12
                year -= 1

        month_start = _first_day_of_month(year, month)
        month_end = _last_day_of_month(year, month)

        projects = await _get_scorecard_projects(db)
        logger.info(
            "capture_started",
            project_count=len(projects),
            year=year,
            month=month,
        )

        captured = 0
        errors = []

        for project in projects:
            try:
                project_start = project.start_date or month_start

                preserved = await MetricsService.get_manual_fields_for_historical_capture(
                    db, project.id, year, month
                )

                # Inject budget_total and tracker EVM fields
                budget = float(project.budget) if project.budget is not None else None
                await inject_evm_into_preserved(
                    preserved, project.id, db, budget, project.start_date, project.end_date
                )

                punctual_jira = await _collect_from_jira(db, project, month_start, month_end)
                punctual_github = await _collect_from_github(db, project, month_start, month_end)
                punctual_data = _build_metrics_data(
                    month_start, month_end, punctual_jira, punctual_github, preserved
                )

                await MetricsService.upsert_metrics(
                    db, project.id, year, month, SnapshotType.PUNCTUAL, config, punctual_data
                )

                cumulative_jira = await _collect_from_jira(db, project, project_start, month_end)
                cumulative_github = await _collect_from_github(db, project, project_start, month_end)
                cumulative_data = _build_metrics_data(
                    project_start, month_end, cumulative_jira, cumulative_github, preserved
                )

                await MetricsService.upsert_metrics(
                    db, project.id, year, month, SnapshotType.CUMULATIVE, config, cumulative_data
                )

                if score_cache:
                    await score_cache.invalidate(str(project.id))

                captured += 1
                logger.info("project_captured", project=project.name)

            except Exception as e:
                # Rollback so the session is usable for the next project.
                # Without this, SQLAlchemy raises PendingRollbackError on every
                # subsequent operation and one bad row poisons the whole run.
                await db.rollback()
                errors.append({"project": project.name, "error": str(e)})
                logger.error("project_capture_failed", project=project.name, error=str(e))

            await asyncio.sleep(5)

        logger.info(
            "capture_completed",
            captured=captured,
            errors=len(errors),
        )

        job_run.status = "completed"
        job_run.completed_at = datetime.now(timezone.utc)
        job_run.projects_checked = len(projects)
        job_run.alerts_sent = captured
        await db.commit()

        return {
            "status": "completed",
            "job_run_id": str(job_run_id),
            "year": year,
            "month": month,
            "captured": captured,
            "errors": len(errors),
            "error_details": errors,
        }

    except Exception as e:
        logger.exception("job_failed")
        # Rollback any half-finished transaction, then write the error status
        # via a raw UPDATE rather than via the ORM instance — `job_run` may be
        # in an inconsistent state after the failed flush. Without this dual
        # safeguard, a poisoned session leaves the row stuck in `running`.
        await db.rollback()
        await db.execute(
            update(ScheduledJobRunDB)
            .where(ScheduledJobRunDB.id == job_run_id)
            .values(
                status="error",
                completed_at=datetime.now(timezone.utc),
                error_message=str(e)[:2000],
            )
        )
        await db.commit()

        return {
            "status": "error",
            "job_run_id": str(job_run_id),
            "error": str(e),
        }
