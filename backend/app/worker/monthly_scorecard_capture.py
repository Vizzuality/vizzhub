"""Monthly scorecard capture cron job.

Runs on the 5th of each month at 2 AM UTC. Captures current month
metrics for all live projects with has_scorecard enabled.
"""

import asyncio
import logging
from datetime import date

from sqlalchemy import select
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
from app.modules.scorecard.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


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

    today = date.today()
    year, month = today.year, today.month

    # Capture previous month if we're in the first 5 days
    if today.day <= 5:
        month -= 1
        if month < 1:
            month = 12
            year -= 1

    month_start = _first_day_of_month(year, month)
    month_end = _last_day_of_month(year, month)

    projects = await _get_scorecard_projects(db)
    logger.info(
        f"Monthly scorecard capture: {len(projects)} projects for {year}-{month:02d}"
    )

    results = []
    errors = []

    for project in projects:
        try:
            project_start = project.start_date or month_start

            preserved = await MetricsService.get_manual_fields_for_historical_capture(
                db, project.id, year, month
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

            results.append(str(project.id))
            logger.info(f"  OK: {project.name}")

        except Exception as e:
            errors.append({"project": project.name, "error": str(e)})
            logger.error(f"  FAIL: {project.name} - {e}")

        await asyncio.sleep(5)

    logger.info(
        f"Monthly scorecard capture completed: "
        f"{len(results)} ok, {len(errors)} errors"
    )

    return {
        "year": year,
        "month": month,
        "captured": len(results),
        "errors": len(errors),
        "error_details": errors,
    }
