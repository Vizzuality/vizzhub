"""Jobs API endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, CurrentUser, DBSession, get_project_or_404
from app.api.schemas.job import (
    CaptureHistoryRequest,
    JobDetailResponse,
    JobResponse,
    JobSummaryResponse,
)
from app.core.models.job import Job, JobStatus, JobType
from app.services.job_service import JobService
from app.utils.constants import MONTH_NAMES
from app.utils.redis import get_redis_pool

router = APIRouter(prefix="/jobs", tags=["jobs"])

JOB_NOT_FOUND = "Job not found"


@router.post(
    "/capture-history", response_model=JobResponse, status_code=status.HTTP_201_CREATED
)
async def create_capture_history_job(
    request: CaptureHistoryRequest,
    current_user: AdminUser,
    db: DBSession,
) -> Job:
    """Create a historical capture job."""
    project = await get_project_or_404(db, request.project_id)

    if (request.to_year, request.to_month) < (request.from_year, request.from_month):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date",
        )

    months = (
        (request.to_year - request.from_year) * 12
        + (request.to_month - request.from_month)
        + 1
    )

    from_month_name = MONTH_NAMES[request.from_month - 1]
    to_month_name = MONTH_NAMES[request.to_month - 1]
    name = f"Historical Capture: {project.name}"
    description = (
        f"{from_month_name} {request.from_year} - "
        f"{to_month_name} {request.to_year} ({months} months)"
    )

    job = await JobService.create_job(
        db=db,
        job_type=JobType.CAPTURE_HISTORY,
        name=name,
        description=description,
        project_id=request.project_id,
        created_by=current_user.user_id if current_user else None,
        params={
            "from_year": request.from_year,
            "from_month": request.from_month,
            "to_year": request.to_year,
            "to_month": request.to_month,
            "force": request.force,
        },
    )

    try:
        pool = await get_redis_pool()
        arq_job = await pool.enqueue_job(
            "capture_history_task",
            str(job.id),
            str(request.project_id),
            request.from_year,
            request.from_month,
            request.to_year,
            request.to_month,
        )
        await JobService.set_arq_job_id(db, job.id, arq_job.job_id)
        await pool.close()
    except Exception as e:
        await JobService.update_status(
            db,
            job.id,
            JobStatus.FAILED,
            error_message=f"Failed to enqueue job: {e}",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start background job. Is Redis running?",
        )

    return job


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> Job:
    """Get job details for polling."""
    job = await JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND,
        )
    return job


@router.get("", response_model=list[JobSummaryResponse])
async def list_jobs(
    current_user: CurrentUser,
    db: DBSession,
    project_id: uuid.UUID | None = None,
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    limit: int = 20,
) -> list[Job]:
    """List jobs with optional filters."""
    return await JobService.list_jobs(
        db,
        project_id=project_id,
        status=status,
        job_type=job_type,
        limit=limit,
    )


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: uuid.UUID,
    current_user: AdminUser,
    db: DBSession,
) -> Job:
    """Cancel a pending job."""
    job = await JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND,
        )

    if job.status != JobStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status '{job.status.value}'",
        )

    return await JobService.update_status(db, job_id, JobStatus.CANCELLED)


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: uuid.UUID,
    current_user: AdminUser,
    db: DBSession,
) -> None:
    """Delete a job. Only completed, failed, or cancelled jobs can be deleted."""
    job = await JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND,
        )

    if job.status in (JobStatus.PENDING, JobStatus.RUNNING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete job with status '{job.status.value}'. Cancel it first.",
        )

    await JobService.delete_job(db, job_id)


@router.post(
    "/{job_id}/retry", response_model=JobResponse, status_code=status.HTTP_201_CREATED
)
async def retry_job(
    job_id: uuid.UUID,
    current_user: AdminUser,
    db: DBSession,
) -> Job:
    """Retry a failed job by creating a new one with same params."""
    original = await JobService.get_job(db, job_id)
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=JOB_NOT_FOUND,
        )

    if original.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed jobs can be retried",
        )

    new_job = await JobService.create_job(
        db=db,
        job_type=original.type,
        name=f"{original.name} (retry)",
        description=original.description,
        project_id=original.project_id,
        created_by=current_user.user_id if current_user else None,
        params=original.params,
    )

    if original.type == JobType.CAPTURE_HISTORY:
        try:
            pool = await get_redis_pool()
            params = original.params
            arq_job = await pool.enqueue_job(
                "capture_history_task",
                str(new_job.id),
                str(original.project_id),
                params["from_year"],
                params["from_month"],
                params["to_year"],
                params["to_month"],
            )
            await JobService.set_arq_job_id(db, new_job.id, arq_job.job_id)
            await pool.close()
        except Exception as e:
            await JobService.update_status(
                db,
                new_job.id,
                JobStatus.FAILED,
                error_message=f"Failed to enqueue job: {e}",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start background job",
            )

    return new_job
