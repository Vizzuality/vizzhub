"""Tests for JobService."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.job import JobStatus, JobType
from app.core.services.job_service import JobService


@pytest.mark.asyncio
async def test_create_job_returns_job_with_pending_status(db_session: AsyncSession):
    """Test that creating a job returns a job with pending status and correct fields."""
    job = await JobService.create_job(
        db=db_session,
        job_type=JobType.CAPTURE_HISTORY,
        name="Test Capture",
        description="Jan 2024 - Jun 2024",
        project_id=None,
        params={"from_year": 2024, "from_month": 1},
    )

    assert job.id is not None
    assert job.type == JobType.CAPTURE_HISTORY
    assert job.status == JobStatus.PENDING
    assert job.name == "Test Capture"
    assert job.description == "Jan 2024 - Jun 2024"
    assert job.progress == 0
    assert job.params == {"from_year": 2024, "from_month": 1}


@pytest.mark.asyncio
async def test_update_progress_updates_job_progress_and_message(
    db_session: AsyncSession,
):
    """Test that updating progress updates the job's progress and message."""
    job = await JobService.create_job(
        db=db_session,
        job_type=JobType.CAPTURE_HISTORY,
        name="Test",
        params={},
    )

    updated = await JobService.update_progress(
        db=db_session,
        job_id=job.id,
        progress=50,
        message="Processing March 2024...",
    )

    assert updated.progress == 50
    assert updated.progress_message == "Processing March 2024..."


@pytest.mark.asyncio
async def test_append_log_adds_timestamped_lines(db_session: AsyncSession):
    """Test that appending logs adds timestamped lines."""
    job = await JobService.create_job(
        db=db_session,
        job_type=JobType.CAPTURE_HISTORY,
        name="Test",
        params={},
    )

    await JobService.append_log(db_session, job.id, "Line 1")
    await JobService.append_log(db_session, job.id, "Line 2")

    refreshed = await JobService.get_job(db_session, job.id)
    assert refreshed is not None
    assert "Line 1" in refreshed.logs
    assert "Line 2" in refreshed.logs
