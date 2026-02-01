"""Service for managing async jobs."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus, JobType


class JobService:
    """Service for job CRUD operations."""

    @staticmethod
    async def create_job(
        db: AsyncSession,
        job_type: JobType,
        name: str,
        params: dict,
        description: str | None = None,
        project_id: uuid.UUID | None = None,
        created_by: str | None = None,
    ) -> Job:
        """Create a new job."""
        job = Job(
            type=job_type,
            name=name,
            description=description,
            project_id=project_id,
            created_by=created_by,
            params=params,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def get_job(db: AsyncSession, job_id: uuid.UUID) -> Job | None:
        """Get job by ID."""
        result = await db.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        project_id: uuid.UUID | None = None,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 20,
    ) -> list[Job]:
        """List jobs with optional filters."""
        query = select(Job).order_by(Job.created_at.desc()).limit(limit)

        if project_id:
            query = query.where(Job.project_id == project_id)
        if status:
            query = query.where(Job.status == status)
        if job_type:
            query = query.where(Job.type == job_type)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        db: AsyncSession,
        job_id: uuid.UUID,
        status: JobStatus,
        error_message: str | None = None,
        error_traceback: str | None = None,
        result: dict | None = None,
    ) -> Job:
        """Update job status."""
        job = await JobService.get_job(db, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = status

        if status == JobStatus.RUNNING and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            job.completed_at = datetime.now(timezone.utc)

        if error_message:
            job.error_message = error_message
        if error_traceback:
            job.error_traceback = error_traceback
        if result:
            job.result = result

        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def update_progress(
        db: AsyncSession,
        job_id: uuid.UUID,
        progress: int,
        message: str | None = None,
    ) -> Job:
        """Update job progress."""
        job = await JobService.get_job(db, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.progress = progress
        if message:
            job.progress_message = message

        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def append_log(
        db: AsyncSession,
        job_id: uuid.UUID,
        log_line: str,
    ) -> Job:
        """Append a line to job logs."""
        job = await JobService.get_job(db, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        new_line = f"[{timestamp}] {log_line}"

        if job.logs:
            job.logs = f"{job.logs}\n{new_line}"
        else:
            job.logs = new_line

        await db.commit()
        await db.refresh(job)
        return job

    @staticmethod
    async def set_arq_job_id(
        db: AsyncSession,
        job_id: uuid.UUID,
        arq_job_id: str,
    ) -> Job:
        """Set the ARQ job ID reference."""
        job = await JobService.get_job(db, job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.arq_job_id = arq_job_id
        await db.commit()
        await db.refresh(job)
        return job
