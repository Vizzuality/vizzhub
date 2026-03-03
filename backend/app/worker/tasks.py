"""ARQ task definitions."""

import asyncio
import traceback
from uuid import UUID

from app.core.models.job import JobStatus
from app.core.services.job_service import JobService
from app.utils.constants import MONTH_NAMES


def generate_month_range(
    from_year: int,
    from_month: int,
    to_year: int,
    to_month: int,
) -> list[tuple[int, int]]:
    """Generate list of (year, month) tuples for a date range."""
    months = []
    year, month = from_year, from_month

    while (year, month) <= (to_year, to_month):
        months.append((year, month))
        month += 1
        if month > 12:
            month = 1
            year += 1

    return months


async def capture_history_task(
    ctx: dict,
    job_id: str,
    project_id: str,
    from_year: int,
    from_month: int,
    to_year: int,
    to_month: int,
) -> dict:
    """Execute historical capture month by month.

    Reuses the internal capture logic from capture.py without HTTP overhead.
    Always upserts metrics (overwrites existing data for each month).

    Args:
        ctx: ARQ context with db session
        job_id: Job UUID string
        project_id: Project UUID string
        from_year: Start year
        from_month: Start month (1-12)
        to_year: End year
        to_month: End month (1-12)

    Returns:
        Report dict with summary of captured months
    """
    from app.api.capture import (
        _build_metrics_data,
        _collect_from_github,
        _collect_from_jira,
        _first_day_of_month,
        _last_day_of_month,
    )
    from app.core.api.deps import get_project_or_404
    from app.config import get_scoring_config
    from app.modules.scorecard.models.metrics import SnapshotType
    from app.services.metrics_service import MetricsService

    db = ctx["db"]
    job_uuid = UUID(job_id)
    project_uuid = UUID(project_id)

    await JobService.update_status(db, job_uuid, JobStatus.RUNNING)

    months = generate_month_range(from_year, from_month, to_year, to_month)
    total_months = len(months)

    results: list[dict] = []
    errors: list[dict] = []

    try:
        project = await get_project_or_404(db, project_uuid)
        config = get_scoring_config()

        for i, (year, month) in enumerate(months):
            month_name = f"{MONTH_NAMES[month - 1]} {year}"
            progress = int((i / total_months) * 100)

            await JobService.update_progress(
                db, job_uuid, progress, f"Processing {month_name}..."
            )

            try:
                month_start = _first_day_of_month(year, month)
                month_end = _last_day_of_month(year, month)
                project_start = project.start_date

                preserved = await MetricsService.get_manual_fields_for_historical_capture(
                    db, project_uuid, year, month
                )

                punctual_jira = await _collect_from_jira(db, project, month_start, month_end)
                punctual_github = await _collect_from_github(db, project, month_start, month_end)
                punctual_data = _build_metrics_data(
                    month_start, month_end, punctual_jira, punctual_github, preserved
                )

                await MetricsService.upsert_metrics(
                    db, project_uuid, year, month, SnapshotType.PUNCTUAL, config, punctual_data
                )

                cumulative_jira = await _collect_from_jira(db, project, project_start, month_end)
                cumulative_github = await _collect_from_github(db, project, project_start, month_end)
                cumulative_data = _build_metrics_data(
                    project_start, month_end, cumulative_jira, cumulative_github, preserved
                )

                await MetricsService.upsert_metrics(
                    db, project_uuid, year, month, SnapshotType.CUMULATIVE, config, cumulative_data
                )

                score_cache = ctx.get("score_cache")
                if score_cache:
                    await score_cache.invalidate(project_id)

                await JobService.append_log(db, job_uuid, f"OK: {month_name}")
                results.append({
                    "year": year,
                    "month": month,
                    "status": "created",
                    "error_message": None,
                })

            except Exception as e:
                error_msg = str(e)
                await JobService.append_log(db, job_uuid, f"ERROR: {month_name} - {error_msg}")
                errors.append({
                    "year": year,
                    "month": month,
                    "status": "error",
                    "error_message": error_msg,
                })

            await asyncio.sleep(5)

        report = {
            "project_id": project_id,
            "requested_range": [
                f"{from_year}-{from_month:02d}",
                f"{to_year}-{to_month:02d}",
            ],
            "summary": {
                "total_months": total_months,
                "snapshots_created": len(results),
                "errors": len(errors),
            },
            "details": results,
            "errors": errors,
        }

        await JobService.update_progress(db, job_uuid, 100, "Completed")
        await JobService.update_status(
            db, job_uuid, JobStatus.COMPLETED, result=report
        )

        return report

    except Exception as e:
        await JobService.update_status(
            db,
            job_uuid,
            JobStatus.FAILED,
            error_message=str(e),
            error_traceback=traceback.format_exc(),
        )
        raise
