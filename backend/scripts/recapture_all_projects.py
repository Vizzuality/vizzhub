"""Enqueue historical capture jobs for all scorecard-enabled projects.

Usage (production via docker exec):
    docker exec hub-backend python scripts/recapture_all_projects.py

What it does:
    1. Finds all live projects with has_scorecard=True
    2. For each project, enqueues a capture_history_task (from start_date to now)
    3. Waits for each job to complete before starting the next
    4. After all captures, recalculates global metrics
    5. Prints a summary of successes and failures

Jobs are visible in the Admin > Jobs page while running.
"""

import asyncio
import sys
from datetime import date

from sqlalchemy import select

from app.config import ScoringConfig, get_scoring_config
from app.core.models.job import Job, JobStatus, JobType
from app.core.models.project import ProjectDB
from app.core.services.job_service import JobService
from app.database import async_session_maker
from app.modules.scorecard.services.global_metrics_service import GlobalMetricsService
from app.utils.redis import get_redis_pool

POLL_INTERVAL = 15
DEFAULT_START_YEAR = 2025
DEFAULT_START_MONTH = 1


async def get_scorecard_projects(db) -> list[ProjectDB]:
    """Get all live projects with scorecard enabled, ordered by name."""
    result = await db.execute(
        select(ProjectDB)
        .where(ProjectDB.status == "live", ProjectDB.has_scorecard.is_(True))
        .order_by(ProjectDB.name)
    )
    return list(result.scalars().all())


async def enqueue_capture(db, pool, project: ProjectDB, to_year: int, to_month: int) -> Job:
    """Create and enqueue a historical capture job for one project."""
    start = project.start_date or date(DEFAULT_START_YEAR, DEFAULT_START_MONTH, 1)
    from_year, from_month = start.year, start.month

    job = await JobService.create_job(
        db=db,
        job_type=JobType.CAPTURE_HISTORY,
        name=f"Batch Recapture: {project.name}",
        description=f"{from_year}-{from_month:02d} to {to_year}-{to_month:02d}",
        project_id=project.id,
        created_by=None,
        params={
            "from_year": from_year,
            "from_month": from_month,
            "to_year": to_year,
            "to_month": to_month,
            "force": True,
        },
    )

    arq_job = await pool.enqueue_job(
        "capture_history_task",
        str(job.id),
        str(project.id),
        from_year,
        from_month,
        to_year,
        to_month,
    )
    await JobService.set_arq_job_id(db, job.id, arq_job.job_id)
    await db.commit()
    return job


async def wait_for_job(db, job_id, project_name: str) -> Job:
    """Poll until job completes or fails."""
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        job = await JobService.get_job(db, job_id)
        if not job:
            print(f"  [ERROR] Job {job_id} not found")
            return None

        if job.status == JobStatus.RUNNING:
            print(f"  ... {project_name}: {job.progress}%", flush=True)

        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return job


async def recalculate_global(db, from_year: int, from_month: int, to_year: int, to_month: int):
    """Recalculate global metrics for the full range."""
    config = get_scoring_config()
    service = GlobalMetricsService(config)
    results = await service.calculate_batch(
        db, from_year, from_month, to_year, to_month
    )
    await db.commit()
    return results


async def main():
    today = date.today()
    to_year, to_month = today.year, today.month

    async with async_session_maker() as db:
        projects = await get_scorecard_projects(db)
        if not projects:
            print("No scorecard-enabled projects found.")
            return

        print(f"Found {len(projects)} projects with scorecard enabled:")
        for p in projects:
            start = p.start_date or date(DEFAULT_START_YEAR, DEFAULT_START_MONTH, 1)
            print(f"  - {p.name} (start: {start})")
        print()

        pool = await get_redis_pool()
        results = []
        earliest_year, earliest_month = to_year, to_month

        for i, project in enumerate(projects, 1):
            start = project.start_date or date(DEFAULT_START_YEAR, DEFAULT_START_MONTH, 1)
            if (start.year, start.month) < (earliest_year, earliest_month):
                earliest_year, earliest_month = start.year, start.month

            print(f"[{i}/{len(projects)}] {project.name} ({start} -> {to_year}-{to_month:02d})")

            try:
                job = await enqueue_capture(db, pool, project, to_year, to_month)
                print(f"  Job {job.id} enqueued")

                completed_job = await wait_for_job(db, job.id, project.name)
                if completed_job and completed_job.status == JobStatus.COMPLETED:
                    result_data = completed_job.result or {}
                    captured = result_data.get("captured", "?")
                    errors = result_data.get("errors", 0)
                    print(f"  OK: {captured} months captured, {errors} errors")
                    results.append((project.name, "OK", f"{captured} months, {errors} errors"))
                elif completed_job:
                    error = completed_job.error_message or "unknown error"
                    print(f"  FAILED: {error}")
                    results.append((project.name, "FAILED", error[:100]))
                else:
                    results.append((project.name, "FAILED", "job disappeared"))
            except Exception as e:
                print(f"  ERROR: {e}")
                results.append((project.name, "ERROR", str(e)[:100]))

        await pool.close()

        # Recalculate global metrics
        print(f"\nRecalculating global metrics ({earliest_year}-{earliest_month:02d} to {to_year}-{to_month:02d})...")
        try:
            global_results = await recalculate_global(db, earliest_year, earliest_month, to_year, to_month)
            print(f"  Global metrics recalculated for {len(global_results)} months")
        except Exception as e:
            print(f"  ERROR recalculating global: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    ok = sum(1 for _, s, _ in results if s == "OK")
    failed = len(results) - ok
    print(f"Total: {len(results)} | OK: {ok} | Failed: {failed}")
    if failed:
        print("\nFailed projects:")
        for name, status, detail in results:
            if status != "OK":
                print(f"  - {name}: {detail}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
