"""Tests for Job model."""

from app.core.models.job import Job, JobStatus, JobType


def test_job_type_enum_has_capture_history():
    """Verify JobType enum has expected capture_history value."""
    assert JobType.CAPTURE_HISTORY.value == "capture_history"


def test_job_status_enum_has_all_statuses():
    """Verify JobStatus enum has all expected status values."""
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.CANCELLED.value == "cancelled"


def test_job_model_creates_with_explicit_values():
    """Verify Job model initializes with explicit values correctly."""
    job = Job(
        type=JobType.CAPTURE_HISTORY,
        status=JobStatus.PENDING,
        name="Test Job",
        params={"test": True},
        progress=0,
    )
    assert job.type == JobType.CAPTURE_HISTORY
    assert job.status == JobStatus.PENDING
    assert job.name == "Test Job"
    assert job.params == {"test": True}
    assert job.progress == 0
    assert job.result is None
    assert job.logs is None
    assert job.error_message is None
    assert job.started_at is None
    assert job.completed_at is None
