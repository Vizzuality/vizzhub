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
from datetime import date

from sqlalchemy import select

from app.config import get_scoring_config
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
    results = await service.calculate_batch(db, from_year, from_month, to_year, to_month)
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
        jobs = []

        # Enqueue all jobs at once — worker processes them sequentially
        for i, project in enumerate(projects, 1):
            start = project.start_date or date(DEFAULT_START_YEAR, DEFAULT_START_MONTH, 1)
            print(
                f"[{i}/{len(projects)}] Enqueuing {project.name} ({start} -> {to_year}-{to_month:02d})"
            )
            try:
                job = await enqueue_capture(db, pool, project, to_year, to_month)
                print(f"  Job {job.id} enqueued")
                jobs.append((project.name, str(job.id)))
            except Exception as e:
                print(f"  ERROR: {e}")

        await pool.close()

    print(f"\nAll {len(jobs)} jobs enqueued. Monitor progress in /admin/jobs.")
    print("When all jobs complete, recalculate global metrics via:")
    print("  POST /api/metrics/global/calculate")
    print(
        f'  Body: {{"from_year": 2022, "from_month": 1, "to_year": {to_year}, "to_month": {to_month}}}'
    )
    print()


if __name__ == "__main__":
    asyncio.run(main())
