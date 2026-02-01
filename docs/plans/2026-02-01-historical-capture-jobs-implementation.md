# Historical Capture Jobs - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement async job processing with ARQ + Redis for batch historical metrics capture.

**Architecture:** FastAPI creates jobs stored in PostgreSQL, enqueues to Redis via ARQ. Separate worker process executes tasks, updates progress. Frontend polls job status every 3s.

**Tech Stack:** ARQ, Redis, PostgreSQL, FastAPI, React Query with polling.

---

## Task 1: Add Redis and ARQ Dependencies

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `docker-compose.yml`
- Modify: `backend/.env.example` (create if not exists)

**Step 1: Add Python dependencies**

In `backend/requirements.txt`, add after the HTTP clients section:

```txt
# Async job queue
arq>=0.25,<1.0.0
redis>=5.0,<6.0.0
```

**Step 2: Add Redis to docker-compose.yml**

Add before the `volumes:` section at the end:

```yaml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER:-scorecard}:${DB_PASSWORD:-scorecard}@db:5432/${DB_NAME:-scorecard}
      - REDIS_HOST=redis
      - REDIS_PORT=6379
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: arq app.worker.settings.WorkerSettings
```

Update `volumes:` section:

```yaml
volumes:
  postgres-data:
  redis-data:
```

**Step 3: Add Redis env to backend service**

In the `backend` service environment section, add:

```yaml
      - REDIS_HOST=redis
      - REDIS_PORT=6379
```

**Step 4: Commit**

```bash
git add backend/requirements.txt docker-compose.yml
git commit -m "feat: add Redis and ARQ dependencies for async jobs"
```

---

## Task 2: Add Redis Configuration

**Files:**
- Modify: `backend/app/config.py`

**Step 1: Add Redis settings to Settings class**

After the GitHub settings (around line 34), add:

```python
    # Redis (for async job queue)
    redis_host: str = ""
    redis_port: int = 6379
    redis_password: str = ""
```

**Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add Redis configuration settings"
```

---

## Task 3: Create Job Model

**Files:**
- Create: `backend/app/models/job.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Write test for Job model**

Create `backend/tests/test_job_model.py`:

```python
"""Tests for Job model."""
import uuid
from datetime import datetime

import pytest

from app.models.job import Job, JobStatus, JobType


def test_job_type_enum():
    assert JobType.CAPTURE_HISTORY.value == "capture_history"


def test_job_status_enum():
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.COMPLETED.value == "completed"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.CANCELLED.value == "cancelled"


def test_job_default_values():
    job = Job(
        type=JobType.CAPTURE_HISTORY,
        name="Test Job",
        params={"test": True},
    )
    assert job.status == JobStatus.PENDING
    assert job.progress == 0
    assert job.result is None
    assert job.logs is None
```

**Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_job_model.py -v
```

Expected: FAIL with "No module named 'app.models.job'"

**Step 3: Create Job model**

Create `backend/app/models/job.py`:

```python
"""Job model for async task tracking."""
import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobType(str, Enum):
    CAPTURE_HISTORY = "capture_history"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(Base):
    """Async job tracking model."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[JobType]
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING)

    # Identification
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(default=None)

    # Context
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), default=None
    )
    created_by: Mapped[str | None] = mapped_column(default=None)

    # Input/Output
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Progress
    progress: Mapped[int] = mapped_column(default=0)
    progress_message: Mapped[str | None] = mapped_column(default=None)

    # Logs and errors
    logs: Mapped[str | None] = mapped_column(Text, default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    error_traceback: Mapped[str | None] = mapped_column(Text, default=None)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)

    # ARQ reference
    arq_job_id: Mapped[str | None] = mapped_column(default=None)

    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_project_id", "project_id"),
        Index("ix_jobs_created_at", "created_at"),
    )
```

**Step 4: Run test to verify it passes**

```bash
cd backend && pytest tests/test_job_model.py -v
```

Expected: PASS

**Step 5: Update models __init__.py**

Add to imports in `backend/app/models/__init__.py`:

```python
from app.models.job import Job, JobStatus, JobType
```

Add to `__all__`:

```python
    "Job",
    "JobStatus",
    "JobType",
```

**Step 6: Create Alembic migration**

```bash
cd backend && alembic revision --autogenerate -m "Add jobs table"
```

**Step 7: Run migration**

```bash
cd backend && alembic upgrade head
```

**Step 8: Commit**

```bash
git add backend/app/models/job.py backend/app/models/__init__.py backend/tests/test_job_model.py backend/alembic/versions/
git commit -m "feat: add Job model for async task tracking"
```

---

## Task 4: Create Job Schemas

**Files:**
- Create: `backend/app/api/schemas/job.py`

**Step 1: Create Pydantic schemas**

Create `backend/app/api/schemas/job.py`:

```python
"""Pydantic schemas for Job API."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.job import JobStatus, JobType


class CaptureHistoryRequest(BaseModel):
    """Request to create a historical capture job."""

    project_id: uuid.UUID
    from_year: int = Field(ge=2020, le=2100)
    from_month: int = Field(ge=1, le=12)
    to_year: int = Field(ge=2020, le=2100)
    to_month: int = Field(ge=1, le=12)
    force: bool = True


class JobResponse(BaseModel):
    """Basic job response."""

    id: uuid.UUID
    type: JobType
    status: JobStatus
    name: str
    progress: int
    created_at: datetime

    model_config = {"from_attributes": True}


class JobDetailResponse(JobResponse):
    """Detailed job response for polling."""

    description: str | None
    project_id: uuid.UUID | None
    params: dict
    result: dict | None
    progress_message: str | None
    logs: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class JobSummaryResponse(BaseModel):
    """Summary for job listing."""

    id: uuid.UUID
    type: JobType
    status: JobStatus
    name: str
    progress: int
    project_id: uuid.UUID | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
```

**Step 2: Commit**

```bash
git add backend/app/api/schemas/job.py
git commit -m "feat: add Job API schemas"
```

---

## Task 5: Create Job Service

**Files:**
- Create: `backend/app/services/job_service.py`
- Create: `backend/tests/test_job_service.py`

**Step 1: Write failing test**

Create `backend/tests/test_job_service.py`:

```python
"""Tests for JobService."""
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus, JobType
from app.services.job_service import JobService


@pytest.mark.asyncio
async def test_create_job(db_session: AsyncSession):
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
    assert job.progress == 0


@pytest.mark.asyncio
async def test_update_job_progress(db_session: AsyncSession):
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
async def test_append_log(db_session: AsyncSession):
    job = await JobService.create_job(
        db=db_session,
        job_type=JobType.CAPTURE_HISTORY,
        name="Test",
        params={},
    )

    await JobService.append_log(db_session, job.id, "Line 1")
    await JobService.append_log(db_session, job.id, "Line 2")

    refreshed = await JobService.get_job(db_session, job.id)
    assert "Line 1" in refreshed.logs
    assert "Line 2" in refreshed.logs
```

**Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_job_service.py -v
```

Expected: FAIL with "No module named 'app.services.job_service'"

**Step 3: Create JobService**

Create `backend/app/services/job_service.py`:

```python
"""Service for managing async jobs."""
import uuid
from datetime import datetime

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
            job.started_at = datetime.utcnow()
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            job.completed_at = datetime.utcnow()

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

        timestamp = datetime.utcnow().strftime("%H:%M:%S")
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
```

**Step 4: Run test to verify it passes**

```bash
cd backend && pytest tests/test_job_service.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/services/job_service.py backend/tests/test_job_service.py
git commit -m "feat: add JobService for async job management"
```

---

## Task 6: Create ARQ Worker Settings

**Files:**
- Create: `backend/app/worker/__init__.py`
- Create: `backend/app/worker/settings.py`

**Step 1: Create worker package**

Create `backend/app/worker/__init__.py`:

```python
"""ARQ worker package."""
```

**Step 2: Create worker settings**

Create `backend/app/worker/settings.py`:

```python
"""ARQ worker configuration."""
from arq.connections import RedisSettings

from app.config import get_settings
from app.database import async_session_maker

settings = get_settings()


async def startup(ctx: dict) -> None:
    """Initialize worker context on startup."""
    ctx["db_session_maker"] = async_session_maker


async def shutdown(ctx: dict) -> None:
    """Cleanup on worker shutdown."""
    pass


async def on_job_start(ctx: dict) -> None:
    """Create DB session before each job."""
    ctx["db"] = ctx["db_session_maker"]()


async def on_job_end(ctx: dict) -> None:
    """Close DB session after each job."""
    if "db" in ctx:
        await ctx["db"].close()


class WorkerSettings:
    """ARQ worker settings."""

    redis_settings = RedisSettings(
        host=settings.redis_host or "localhost",
        port=settings.redis_port,
        password=settings.redis_password or None,
    )

    on_startup = startup
    on_shutdown = shutdown
    on_job_start = on_job_start
    on_job_end = on_job_end

    # Import functions here to avoid circular imports
    # Will be populated in Task 7
    functions: list = []

    max_jobs = 5
    job_timeout = 3600  # 1 hour
    keep_result = 86400  # 24 hours
    retry_jobs = True
    max_tries = 2
```

**Step 3: Commit**

```bash
git add backend/app/worker/
git commit -m "feat: add ARQ worker settings"
```

---

## Task 7: Create Capture History Task

**Files:**
- Create: `backend/app/worker/tasks.py`
- Modify: `backend/app/worker/settings.py`

**Step 1: Create helper for month range**

Create `backend/app/worker/tasks.py`:

```python
"""ARQ task definitions."""
import asyncio
import traceback
from datetime import date

from app.models.job import JobStatus
from app.services.job_service import JobService

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


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
    force: bool = True,
) -> dict:
    """
    Execute historical capture month by month.

    Reuses the internal capture logic from capture.py without HTTP overhead.
    """
    from uuid import UUID

    from app.api.capture import (
        _collect_from_jira,
        _collect_from_github,
        _build_metrics_data,
        _first_day_of_month,
        _last_day_of_month,
    )
    from app.api.deps import get_project_or_404
    from app.config import get_scoring_config
    from app.models.metrics import SnapshotType
    from app.services.metrics_service import MetricsService

    db = ctx["db"]
    job_uuid = UUID(job_id)
    project_uuid = UUID(project_id)

    # Mark job as running
    await JobService.update_status(db, job_uuid, JobStatus.RUNNING)

    months = generate_month_range(from_year, from_month, to_year, to_month)
    total_months = len(months)

    results = []
    errors = []

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
                # Calculate date ranges
                month_start = _first_day_of_month(year, month)
                month_end = _last_day_of_month(year, month)
                project_start = project.start_date

                # Get preserved manual fields
                preserved = await MetricsService.get_manual_fields_for_historical_capture(
                    db, project_uuid, year, month
                )

                # Collect punctual metrics
                punctual_jira = await _collect_from_jira(db, project, month_start, month_end)
                punctual_github = await _collect_from_github(project, month_start, month_end)
                punctual_data = _build_metrics_data(
                    month_start, month_end, punctual_jira, punctual_github, preserved
                )

                await MetricsService.upsert_metrics(
                    db, project_uuid, year, month, SnapshotType.PUNCTUAL, config, punctual_data
                )

                # Collect cumulative metrics
                cumulative_jira = await _collect_from_jira(db, project, project_start, month_end)
                cumulative_github = await _collect_from_github(project, project_start, month_end)
                cumulative_data = _build_metrics_data(
                    project_start, month_end, cumulative_jira, cumulative_github, preserved
                )

                await MetricsService.upsert_metrics(
                    db, project_uuid, year, month, SnapshotType.CUMULATIVE, config, cumulative_data
                )

                await JobService.append_log(db, job_uuid, f"✓ {month_name}: OK")
                results.append({
                    "year": year,
                    "month": month,
                    "status": "created",
                    "error_message": None,
                })

            except Exception as e:
                error_msg = str(e)
                await JobService.append_log(db, job_uuid, f"✗ {month_name}: {error_msg}")
                errors.append({
                    "year": year,
                    "month": month,
                    "status": "error",
                    "error_message": error_msg,
                })

            # Rate limiting between months
            await asyncio.sleep(5)

        # Build final report
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
```

**Step 2: Register task in worker settings**

Update `backend/app/worker/settings.py`, replace the empty functions list:

```python
    # Import functions here to avoid circular imports
    @staticmethod
    def functions():
        from app.worker.tasks import capture_history_task
        return [capture_history_task]
```

Actually, ARQ needs the functions as a list attribute. Update the class:

```python
class WorkerSettings:
    """ARQ worker settings."""

    redis_settings = RedisSettings(
        host=settings.redis_host or "localhost",
        port=settings.redis_port,
        password=settings.redis_password or None,
    )

    on_startup = startup
    on_shutdown = shutdown
    on_job_start = on_job_start
    on_job_end = on_job_end

    max_jobs = 5
    job_timeout = 3600  # 1 hour
    keep_result = 86400  # 24 hours
    retry_jobs = True
    max_tries = 2


# Functions must be at module level for ARQ
def get_worker_settings():
    """Get worker settings with functions loaded."""
    from app.worker.tasks import capture_history_task

    WorkerSettings.functions = [capture_history_task]
    return WorkerSettings
```

**Step 3: Commit**

```bash
git add backend/app/worker/tasks.py backend/app/worker/settings.py
git commit -m "feat: add capture_history_task for batch historical capture"
```

---

## Task 8: Create Jobs API Endpoints

**Files:**
- Create: `backend/app/api/jobs.py`
- Modify: `backend/app/main.py`

**Step 1: Create jobs router**

Create `backend/app/api/jobs.py`:

```python
"""Jobs API endpoints."""
import uuid

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.api.schemas.job import (
    CaptureHistoryRequest,
    JobDetailResponse,
    JobResponse,
    JobSummaryResponse,
)
from app.config import get_settings
from app.models.job import Job, JobStatus, JobType
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


async def get_redis_pool():
    """Get ARQ Redis connection pool."""
    settings = get_settings()
    return await create_pool(
        RedisSettings(
            host=settings.redis_host or "localhost",
            port=settings.redis_port,
            password=settings.redis_password or None,
        )
    )


@router.post("/capture-history", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_capture_history_job(
    request: CaptureHistoryRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> Job:
    """Create a historical capture job."""
    from app.api.deps import get_project_or_404

    # Validate project exists
    project = await get_project_or_404(db, request.project_id)

    # Validate date range
    if (request.to_year, request.to_month) < (request.from_year, request.from_month):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date",
        )

    # Calculate month count
    months = (request.to_year - request.from_year) * 12 + (request.to_month - request.from_month) + 1

    # Generate name and description
    from_month_name = MONTH_NAMES[request.from_month - 1]
    to_month_name = MONTH_NAMES[request.to_month - 1]
    name = f"Historical Capture: {project.name}"
    description = f"{from_month_name} {request.from_year} - {to_month_name} {request.to_year} ({months} months)"

    # Create job record
    job = await JobService.create_job(
        db=db,
        job_type=JobType.CAPTURE_HISTORY,
        name=name,
        description=description,
        project_id=request.project_id,
        created_by=current_user.get("user_id") if current_user else None,
        params={
            "from_year": request.from_year,
            "from_month": request.from_month,
            "to_year": request.to_year,
            "to_month": request.to_month,
            "force": request.force,
        },
    )

    # Enqueue to ARQ
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
            request.force,
        )
        await JobService.set_arq_job_id(db, job.id, arq_job.job_id)
        await pool.close()
    except Exception as e:
        # Mark job as failed if we can't enqueue
        await JobService.update_status(
            db, job.id, JobStatus.FAILED,
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
    db: DBSession,
) -> Job:
    """Get job details for polling."""
    job = await JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job


@router.get("/", response_model=list[JobSummaryResponse])
async def list_jobs(
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
    db: DBSession,
) -> Job:
    """Cancel a pending job."""
    job = await JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.status != JobStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status '{job.status.value}'",
        )

    return await JobService.update_status(db, job_id, JobStatus.CANCELLED)


@router.post("/{job_id}/retry", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def retry_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> Job:
    """Retry a failed job by creating a new one with same params."""
    original = await JobService.get_job(db, job_id)
    if not original:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if original.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed jobs can be retried",
        )

    # Create new job with same params
    new_job = await JobService.create_job(
        db=db,
        job_type=original.type,
        name=f"{original.name} (retry)",
        description=original.description,
        project_id=original.project_id,
        created_by=current_user.get("user_id") if current_user else None,
        params=original.params,
    )

    # Enqueue based on job type
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
                params.get("force", True),
            )
            await JobService.set_arq_job_id(db, new_job.id, arq_job.job_id)
            await pool.close()
        except Exception as e:
            await JobService.update_status(
                db, new_job.id, JobStatus.FAILED,
                error_message=f"Failed to enqueue job: {e}",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start background job",
            )

    return new_job
```

**Step 2: Register router in main.py**

Add to imports in `backend/app/main.py`:

```python
from app.api.jobs import router as jobs_router
```

Add after other router includes:

```python
app.include_router(jobs_router, prefix="/api")
```

**Step 3: Commit**

```bash
git add backend/app/api/jobs.py backend/app/main.py
git commit -m "feat: add Jobs API endpoints"
```

---

## Task 9: Add Frontend Types

**Files:**
- Modify: `frontend/src/types/index.ts`

**Step 1: Add Job types**

Add at the end of `frontend/src/types/index.ts`:

```typescript
// Job types for async task tracking
export type JobType = 'capture_history';

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobResponse {
  id: string;
  type: JobType;
  status: JobStatus;
  name: string;
  progress: number;
  created_at: string;
}

export interface JobDetailResponse extends JobResponse {
  description: string | null;
  project_id: string | null;
  params: Record<string, unknown>;
  result: CaptureReport | null;
  progress_message: string | null;
  logs: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface JobSummaryResponse {
  id: string;
  type: JobType;
  status: JobStatus;
  name: string;
  progress: number;
  project_id: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface CreateCaptureHistoryJobRequest {
  project_id: string;
  from_year: number;
  from_month: number;
  to_year: number;
  to_month: number;
  force?: boolean;
}
```

**Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add Job types for async task tracking"
```

---

## Task 10: Add Jobs API Service

**Files:**
- Modify: `frontend/src/services/api.ts`

**Step 1: Add jobsApi**

Add after `captureApi` in `frontend/src/services/api.ts`:

```typescript
export const jobsApi = {
  createCaptureHistory: async (
    request: CreateCaptureHistoryJobRequest,
  ): Promise<JobResponse> => {
    const response = await api.post<JobResponse>('/jobs/capture-history', request);
    return response.data;
  },

  getJob: async (jobId: string): Promise<JobDetailResponse> => {
    const response = await api.get<JobDetailResponse>(`/jobs/${jobId}`);
    return response.data;
  },

  listJobs: async (projectId?: string): Promise<JobSummaryResponse[]> => {
    const params = projectId ? { project_id: projectId } : {};
    const response = await api.get<JobSummaryResponse[]>('/jobs', { params });
    return response.data;
  },

  cancelJob: async (jobId: string): Promise<JobResponse> => {
    const response = await api.post<JobResponse>(`/jobs/${jobId}/cancel`);
    return response.data;
  },

  retryJob: async (jobId: string): Promise<JobResponse> => {
    const response = await api.post<JobResponse>(`/jobs/${jobId}/retry`);
    return response.data;
  },
};
```

**Step 2: Add imports**

Update the import at the top:

```typescript
import type {
  // ... existing imports
  JobResponse,
  JobDetailResponse,
  JobSummaryResponse,
  CreateCaptureHistoryJobRequest,
} from '../types';
```

**Step 3: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: add Jobs API service"
```

---

## Task 11: Add Query Keys and Hooks

**Files:**
- Modify: `frontend/src/hooks/queryKeys.ts`
- Create: `frontend/src/hooks/useJobs.ts`

**Step 1: Add job query keys**

Add to `frontend/src/hooks/queryKeys.ts`:

```typescript
  jobs: {
    all: ['jobs'] as const,
    byProject: (projectId: string) => ['jobs', 'project', projectId] as const,
    detail: (jobId: string) => ['jobs', 'detail', jobId] as const,
  },
```

**Step 2: Create useJobs hook**

Create `frontend/src/hooks/useJobs.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../services/api';
import { queryKeys } from './queryKeys';
import type {
  CreateCaptureHistoryJobRequest,
  JobDetailResponse,
  JobSummaryResponse,
} from '../types';

interface UseJobStatusOptions {
  enabled?: boolean;
}

/**
 * Hook for polling job status.
 * Automatically polls every 3s while job is pending/running.
 */
export function useJobStatus(
  jobId: string | null,
  options: UseJobStatusOptions = {},
) {
  return useQuery({
    queryKey: queryKeys.jobs.detail(jobId!),
    queryFn: () => jobsApi.getJob(jobId!),
    enabled: !!jobId && options.enabled !== false,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'pending' || status === 'running') {
        return 3000;
      }
      return false;
    },
  });
}

/**
 * Hook for creating a historical capture job.
 */
export function useCaptureHistoryJob(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: Omit<CreateCaptureHistoryJobRequest, 'project_id'>) =>
      jobsApi.createCaptureHistory({ ...request, project_id: projectId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.byProject(projectId) });
    },
  });
}

/**
 * Hook for listing jobs for a project.
 */
export function useProjectJobs(projectId: string) {
  return useQuery({
    queryKey: queryKeys.jobs.byProject(projectId),
    queryFn: () => jobsApi.listJobs(projectId),
  });
}

/**
 * Hook for cancelling a job.
 */
export function useCancelJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (jobId: string) => jobsApi.cancelJob(jobId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.detail(data.id) });
    },
  });
}
```

**Step 3: Commit**

```bash
git add frontend/src/hooks/queryKeys.ts frontend/src/hooks/useJobs.ts
git commit -m "feat: add useJobs hooks with polling"
```

---

## Task 12: Create Historical Capture UI Component

**Files:**
- Create: `frontend/src/components/ProjectDetail/HistoricalCaptureSection.tsx`
- Modify: `frontend/src/components/ProjectDetail/SnapshotManager.tsx`

**Step 1: Create HistoricalCaptureSection component**

Create `frontend/src/components/ProjectDetail/HistoricalCaptureSection.tsx`:

```tsx
import { useState } from 'react';
import { useCaptureHistoryJob, useJobStatus } from '../../hooks/useJobs';
import { MONTHS } from '../../constants/dates';
import { getYearOptions } from '../../utils/dateUtils';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { History, Loader2, ChevronDown, ChevronRight } from 'lucide-react';

interface HistoricalCaptureSectionProps {
  projectId: string;
}

export default function HistoricalCaptureSection({
  projectId,
}: HistoricalCaptureSectionProps): JSX.Element {
  const currentDate = new Date();
  const [isExpanded, setIsExpanded] = useState(false);

  // Date range state
  const [fromYear, setFromYear] = useState(currentDate.getFullYear());
  const [fromMonth, setFromMonth] = useState(1);
  const [toYear, setToYear] = useState(currentDate.getFullYear());
  const [toMonth, setToMonth] = useState(currentDate.getMonth() + 1);

  // Active job state
  const [activeJobId, setActiveJobId] = useState<string | null>(null);

  // Hooks
  const captureHistoryJob = useCaptureHistoryJob(projectId);
  const { data: job } = useJobStatus(activeJobId);

  const isJobActive = job?.status === 'pending' || job?.status === 'running';
  const years = getYearOptions();

  const handleStartCapture = async () => {
    const result = await captureHistoryJob.mutateAsync({
      from_year: fromYear,
      from_month: fromMonth,
      to_year: toYear,
      to_month: toMonth,
      force: true,
    });
    setActiveJobId(result.id);
  };

  // Calculate month count for display
  const monthCount =
    (toYear - fromYear) * 12 + (toMonth - fromMonth) + 1;

  return (
    <Card>
      <CardHeader
        className="cursor-pointer select-none"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <CardTitle className="flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="h-5 w-5" />
          ) : (
            <ChevronRight className="h-5 w-5" />
          )}
          <History className="h-5 w-5" />
          Batch Historical Capture
        </CardTitle>
        <CardDescription>
          {isExpanded
            ? 'Capture metrics for multiple months at once. This runs in the background.'
            : 'Click to capture metrics for a date range'}
        </CardDescription>
      </CardHeader>

      {isExpanded && (
        <CardContent className="space-y-4">
          {/* Date range selectors */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-muted-foreground">From</span>

            <select
              value={fromMonth}
              onChange={(e) => setFromMonth(Number(e.target.value))}
              disabled={isJobActive}
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {MONTHS.map((month, i) => (
                <option key={i} value={i + 1}>
                  {month}
                </option>
              ))}
            </select>

            <select
              value={fromYear}
              onChange={(e) => setFromYear(Number(e.target.value))}
              disabled={isJobActive}
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {years.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>

            <span className="text-sm text-muted-foreground">to</span>

            <select
              value={toMonth}
              onChange={(e) => setToMonth(Number(e.target.value))}
              disabled={isJobActive}
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {MONTHS.map((month, i) => (
                <option key={i} value={i + 1}>
                  {month}
                </option>
              ))}
            </select>

            <select
              value={toYear}
              onChange={(e) => setToYear(Number(e.target.value))}
              disabled={isJobActive}
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              {years.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>

          {/* Month count info */}
          {monthCount > 0 && !isJobActive && (
            <p className="text-sm text-muted-foreground">
              Will capture {monthCount} month{monthCount > 1 ? 's' : ''}.
              Estimated time: ~{Math.ceil(monthCount * 2.5)} minutes.
            </p>
          )}

          {/* Start button */}
          {!isJobActive && (
            <Button
              onClick={handleStartCapture}
              disabled={captureHistoryJob.isPending || monthCount <= 0}
            >
              {captureHistoryJob.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <History className="mr-2 h-4 w-4" />
                  Start Batch Capture
                </>
              )}
            </Button>
          )}

          {/* Progress display */}
          {job && isJobActive && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span>{job.progress_message || 'Initializing...'}</span>
                <span>{job.progress}%</span>
              </div>
              <Progress value={job.progress} />
              <p className="text-xs text-muted-foreground">
                This process runs in the background. You can close this page.
              </p>
            </div>
          )}

          {/* Completed state */}
          {job?.status === 'completed' && (
            <div className="text-sm text-green-600 bg-green-50 p-3 rounded">
              ✓ Capture completed.{' '}
              {job.result?.summary?.snapshots_created ?? 0} snapshots created.
              {(job.result?.summary?.errors ?? 0) > 0 && (
                <span className="text-amber-600">
                  {' '}({job.result?.summary?.errors} errors)
                </span>
              )}
            </div>
          )}

          {/* Failed state */}
          {job?.status === 'failed' && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
              ✗ Capture failed: {job.error_message}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
```

**Step 2: Import in SnapshotManager**

Modify `frontend/src/components/ProjectDetail/SnapshotManager.tsx`.

Add import at top:

```typescript
import HistoricalCaptureSection from './HistoricalCaptureSection';
```

Update the return to include the new component. Replace the outer `div` with:

```tsx
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Existing Historic Metrics card */}
        <Card>
          {/* ... existing card content ... */}
        </Card>

        {/* Existing Export card */}
        <Card>
          {/* ... existing export card ... */}
        </Card>
      </div>

      {/* New Historical Capture Section */}
      <HistoricalCaptureSection projectId={projectId} />
    </div>
  );
```

**Step 3: Commit**

```bash
git add frontend/src/components/ProjectDetail/HistoricalCaptureSection.tsx frontend/src/components/ProjectDetail/SnapshotManager.tsx
git commit -m "feat: add HistoricalCaptureSection UI component"
```

---

## Task 13: Integration Test

**Files:**
- Create: `backend/tests/test_jobs_integration.py`

**Step 1: Write integration test**

Create `backend/tests/test_jobs_integration.py`:

```python
"""Integration tests for Jobs API."""
import pytest
from httpx import AsyncClient

from app.models.job import JobStatus, JobType


@pytest.mark.asyncio
async def test_create_capture_history_job(client: AsyncClient, test_project):
    """Test creating a capture history job."""
    response = await client.post(
        "/api/jobs/capture-history",
        json={
            "project_id": str(test_project.id),
            "from_year": 2024,
            "from_month": 1,
            "to_year": 2024,
            "to_month": 3,
            "force": True,
        },
    )

    # May fail if Redis not running - that's OK for unit tests
    if response.status_code == 500:
        assert "Redis" in response.json()["detail"]
        return

    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "capture_history"
    assert data["status"] == "pending"
    assert "Historical Capture" in data["name"]


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient):
    """Test getting non-existent job."""
    response = await client.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs_empty(client: AsyncClient):
    """Test listing jobs when none exist."""
    response = await client.get("/api/jobs/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

**Step 2: Run tests**

```bash
cd backend && pytest tests/test_jobs_integration.py -v
```

**Step 3: Commit**

```bash
git add backend/tests/test_jobs_integration.py
git commit -m "test: add Jobs API integration tests"
```

---

## Task 14: Update .env.example

**Files:**
- Modify: `backend/.env.example` (or create if doesn't exist)

**Step 1: Add Redis variables**

Add to `.env.example`:

```bash
# Redis (for async job queue)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
```

**Step 2: Commit**

```bash
git add backend/.env.example
git commit -m "docs: add Redis config to .env.example"
```

---

## Task 15: Final Verification

**Step 1: Install dependencies**

```bash
cd backend && pip install -r requirements.txt
```

**Step 2: Run all tests**

```bash
cd backend && pytest -v
```

**Step 3: Start services and verify**

```bash
# Terminal 1: Start Redis (if not using docker)
redis-server

# Terminal 2: Run migrations and start backend
cd backend && alembic upgrade head && python run_server.py

# Terminal 3: Start worker
cd backend && arq app.worker.settings.WorkerSettings

# Terminal 4: Start frontend
cd frontend && npm run dev
```

**Step 4: Manual test**

1. Open browser to `http://localhost:5173`
2. Navigate to a project detail page
3. Expand "Batch Historical Capture" section
4. Select a date range
5. Click "Start Batch Capture"
6. Verify progress updates every 3 seconds

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete historical capture jobs implementation"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add Redis/ARQ dependencies | requirements.txt, docker-compose.yml |
| 2 | Redis configuration | config.py |
| 3 | Job model | models/job.py |
| 4 | Job schemas | api/schemas/job.py |
| 5 | Job service | services/job_service.py |
| 6 | Worker settings | worker/settings.py |
| 7 | Capture history task | worker/tasks.py |
| 8 | Jobs API endpoints | api/jobs.py |
| 9 | Frontend types | types/index.ts |
| 10 | Jobs API service | services/api.ts |
| 11 | Query keys and hooks | hooks/queryKeys.ts, hooks/useJobs.ts |
| 12 | UI component | HistoricalCaptureSection.tsx |
| 13 | Integration tests | tests/test_jobs_integration.py |
| 14 | Environment docs | .env.example |
| 15 | Final verification | - |
