# Historical Capture Jobs - Design Document

## Overview

Service to populate the database with historical metrics by iterating through a date range month by month, using existing collectors. Built on ARQ + Redis for async job processing.

## Requirements

- Capture metrics month by month (not date range filtering) for consistency
- Do not modify existing collectors - only orchestrate them
- Respect API rate limiting (5s delay between months)
- Jobs survive server restarts
- Frontend shows real-time progress

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   FastAPI   │────▶│    Redis    │
│  (polling)  │◀────│   (API)     │     │   (queue)   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                           │                   │
                           ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │ PostgreSQL  │◀────│ ARQ Worker  │
                    │   (jobs)    │     │  (process)  │
                    └─────────────┘     └─────────────┘
```

## Data Model

### Jobs Table

```python
class JobType(str, Enum):
    CAPTURE_HISTORY = "capture_history"

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[JobType]
    status: Mapped[JobStatus] = mapped_column(default=JobStatus.PENDING)

    # Identification
    name: Mapped[str]                    # "Historical Capture FIP"
    description: Mapped[str | None]      # "Jan 2024 - Jun 2024 (6 months)"

    # Context
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    created_by: Mapped[str | None]

    # Input/Output (JSON)
    params: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB)

    # Progress
    progress: Mapped[int] = mapped_column(default=0)  # 0-100
    progress_message: Mapped[str | None]

    # Logs and errors
    logs: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None]
    error_traceback: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]

    # ARQ reference
    arq_job_id: Mapped[str | None]
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/jobs/capture-history` | Create historical capture job |
| GET | `/jobs/{job_id}` | Get job status (for polling) |
| GET | `/jobs` | List jobs (with filters) |
| POST | `/jobs/{job_id}/cancel` | Cancel pending job |
| POST | `/jobs/{job_id}/retry` | Retry failed job |

### Request/Response Schemas

```python
class CaptureHistoryRequest(BaseModel):
    project_id: uuid.UUID
    from_year: int
    from_month: int
    to_year: int
    to_month: int
    force: bool = True

class JobResponse(BaseModel):
    id: uuid.UUID
    type: JobType
    status: JobStatus
    progress: int
    created_at: datetime

class JobDetailResponse(JobResponse):
    name: str
    description: str | None
    params: dict
    result: dict | None
    progress_message: str | None
    logs: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
```

## Worker Implementation

### Task Flow

```python
async def capture_history_task(ctx, job_id, project_id, from_year, from_month, to_year, to_month, force):
    months = generate_month_range(from_year, from_month, to_year, to_month)

    for i, (year, month) in enumerate(months):
        # Update progress
        progress = int((i / len(months)) * 100)
        await update_job_progress(db, job_id, progress, f"Processing {month_name}...")

        try:
            # Reuse existing capture-period logic
            await execute_capture_period(db, project_id, year, month, force)
            await append_job_log(db, job_id, f"✓ {month_name}: OK")
        except Exception as e:
            await append_job_log(db, job_id, f"✗ {month_name}: {e}")
            # Continue with next month

        # Rate limiting
        await asyncio.sleep(5)

    return build_capture_report(project_id, months, results)
```

### Worker Settings

```python
class WorkerSettings:
    redis_settings = RedisSettings(host=settings.redis_host, port=settings.redis_port)
    functions = [capture_history_task]
    max_jobs = 5
    job_timeout = 3600  # 1 hour
    retry_jobs = True
    max_tries = 2
```

## Frontend

### Hook with Polling

```typescript
function useJobStatus(jobId: string | null) {
  return useQuery({
    queryKey: queryKeys.jobs.detail(jobId!),
    queryFn: () => jobsApi.getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'pending' || status === 'running') return 3000;
      return false;
    },
  });
}
```

### UI Component

- Date range selectors (from month/year to month/year)
- Start button (disabled while job active)
- Progress bar with message
- Success/error states

Location: Below existing `SnapshotManager` in project detail page.

## Infrastructure

### Docker Compose

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  worker:
    build: ./backend
    command: arq app.worker.settings.WorkerSettings
    depends_on:
      - redis
      - db
```

### Environment Variables

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
```

## Files to Create/Modify

| File | Action |
|------|--------|
| `docker-compose.yml` | Add Redis + worker services |
| `backend/requirements.txt` | Add `arq`, `redis` |
| `backend/app/config.py` | Add Redis config |
| `backend/app/models/job.py` | Create Job model |
| `backend/app/worker/settings.py` | Create ARQ config |
| `backend/app/worker/tasks.py` | Create capture_history_task |
| `backend/app/worker/context.py` | Create DB session helpers |
| `backend/app/api/jobs.py` | Create CRUD endpoints |
| `backend/app/api/schemas/job.py` | Create Pydantic schemas |
| `frontend/src/services/api.ts` | Add jobsApi |
| `frontend/src/hooks/useJobs.ts` | Create hooks |
| `frontend/src/hooks/queryKeys.ts` | Add job keys |
| `frontend/src/types/index.ts` | Add Job types |
| `frontend/src/components/.../HistoricalCaptureSection.tsx` | Create UI |

## Out of Scope

- Admin view for all jobs
- WebSocket push notifications
- Scheduled cron jobs
- Retry from UI
