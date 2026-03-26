"""Tests for Scheduled Jobs API endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.modules.scorecard.models.slack import ScheduledJobRunDB


class TestListScheduledJobs:
    """Tests for GET /admin/jobs/scheduled endpoint."""

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_empty(self, client: AsyncClient) -> None:
        """List scheduled jobs returns all known jobs with no last run."""
        response = await client.get("/api/admin/jobs/scheduled")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6

        job_names = {job["name"] for job in data}
        assert "check_dependabot_alerts" in job_names
        assert "check_business_alerts" in job_names
        assert "collect_iso_snapshot" in job_names
        assert "monthly_scorecard_capture" in job_names
        assert "fetch_exchange_rates" in job_names
        assert "send_monthly_report_reminder" in job_names

        for job in data:
            assert "name" in job
            assert "schedule" in job
            assert "description" in job
            assert job["last_run"] is None

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_with_last_run(
        self, client: AsyncClient, db_session
    ) -> None:
        """List scheduled jobs includes last run info when available."""
        now = datetime.now(timezone.utc)
        job_run = ScheduledJobRunDB(
            job_name="check_dependabot_alerts",
            started_at=now,
            completed_at=now,
            status="completed",
            projects_checked=5,
            alerts_sent=3,
        )
        db_session.add(job_run)
        await db_session.commit()
        await db_session.refresh(job_run)

        response = await client.get("/api/admin/jobs/scheduled")
        assert response.status_code == 200
        data = response.json()

        dependabot_job = next(
            (j for j in data if j["name"] == "check_dependabot_alerts"), None
        )
        assert dependabot_job is not None
        assert dependabot_job["last_run"] is not None
        assert dependabot_job["last_run"]["status"] == "completed"
        assert dependabot_job["last_run"]["projects_checked"] == 5
        assert dependabot_job["last_run"]["alerts_sent"] == 3
        assert dependabot_job["last_run"]["error_message"] is None

        business_job = next(
            (j for j in data if j["name"] == "check_business_alerts"), None
        )
        assert business_job is not None
        assert business_job["last_run"] is None

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_returns_most_recent_run(
        self, client: AsyncClient, db_session
    ) -> None:
        """List scheduled jobs returns only the most recent run."""
        now = datetime.now(timezone.utc)

        old_run = ScheduledJobRunDB(
            job_name="check_dependabot_alerts",
            started_at=datetime(2024, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 1, 8, 5, 0, tzinfo=timezone.utc),
            status="completed",
            projects_checked=2,
            alerts_sent=1,
        )
        new_run = ScheduledJobRunDB(
            job_name="check_dependabot_alerts",
            started_at=now,
            completed_at=now,
            status="error",
            projects_checked=0,
            alerts_sent=0,
            error_message="Connection failed",
        )
        db_session.add_all([old_run, new_run])
        await db_session.commit()

        response = await client.get("/api/admin/jobs/scheduled")
        assert response.status_code == 200
        data = response.json()

        dependabot_job = next(
            (j for j in data if j["name"] == "check_dependabot_alerts"), None
        )
        assert dependabot_job["last_run"]["status"] == "error"
        assert dependabot_job["last_run"]["error_message"] == "Connection failed"

    @pytest.mark.asyncio
    async def test_list_scheduled_jobs_job_info_fields(
        self, client: AsyncClient
    ) -> None:
        """List scheduled jobs returns correct job info fields."""
        response = await client.get("/api/admin/jobs/scheduled")
        assert response.status_code == 200
        data = response.json()

        dependabot_job = next(
            (j for j in data if j["name"] == "check_dependabot_alerts"), None
        )
        assert dependabot_job is not None
        assert "Daily at 8:00 AM" in dependabot_job["schedule"]
        assert "Dependabot" in dependabot_job["description"]

        business_job = next(
            (j for j in data if j["name"] == "check_business_alerts"), None
        )
        assert business_job is not None
        assert "Daily at 9:00 AM" in business_job["schedule"]
        assert "budget" in business_job["description"].lower()


class TestTriggerScheduledJob:
    """Tests for POST /admin/jobs/scheduled/{job_name}/run endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_job_unknown_name(self, client: AsyncClient) -> None:
        """Trigger job returns 404 for unknown job name."""
        response = await client.post("/api/admin/jobs/scheduled/unknown_job/run")
        assert response.status_code == 404
        assert "Unknown scheduled job" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_trigger_job_success(self, client: AsyncClient) -> None:
        """Trigger job enqueues job successfully."""
        mock_job = MagicMock()
        mock_job.job_id = "arq-job-123"

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=mock_job)
        mock_pool.close = AsyncMock()

        with patch(
            "app.modules.scorecard.api.scheduled_jobs.get_redis_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ):
            response = await client.post(
                "/api/admin/jobs/scheduled/check_dependabot_alerts/run"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "enqueued" in data["message"]
        assert data["job_id"] == "arq-job-123"

        mock_pool.enqueue_job.assert_called_once_with("check_dependabot_alerts")
        mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_job_already_queued(self, client: AsyncClient) -> None:
        """Trigger job returns failure when job is already queued."""
        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=None)
        mock_pool.close = AsyncMock()

        with patch(
            "app.modules.scorecard.api.scheduled_jobs.get_redis_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ):
            response = await client.post(
                "/api/admin/jobs/scheduled/check_business_alerts/run"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "could not be enqueued" in data["message"]
        assert data["job_id"] is None

    @pytest.mark.asyncio
    async def test_trigger_job_redis_error(self, client: AsyncClient) -> None:
        """Trigger job returns 500 when Redis is unavailable."""
        with patch(
            "app.modules.scorecard.api.scheduled_jobs.get_redis_pool",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Redis connection refused"),
        ):
            response = await client.post(
                "/api/admin/jobs/scheduled/check_dependabot_alerts/run"
            )

        assert response.status_code == 500
        assert "Failed to enqueue job" in response.json()["detail"]
        assert "Redis" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_trigger_both_jobs(self, client: AsyncClient) -> None:
        """Both scheduled jobs can be triggered."""
        mock_job = MagicMock()
        mock_job.job_id = "test-job-id"

        mock_pool = AsyncMock()
        mock_pool.enqueue_job = AsyncMock(return_value=mock_job)
        mock_pool.close = AsyncMock()

        with patch(
            "app.modules.scorecard.api.scheduled_jobs.get_redis_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ):
            response1 = await client.post(
                "/api/admin/jobs/scheduled/check_dependabot_alerts/run"
            )
            response2 = await client.post(
                "/api/admin/jobs/scheduled/check_business_alerts/run"
            )

        assert response1.status_code == 200
        assert response1.json()["success"] is True

        assert response2.status_code == 200
        assert response2.json()["success"] is True


class TestScheduledJobsWithRunHistory:
    """Tests for scheduled jobs with various run states."""

    @pytest.mark.asyncio
    async def test_running_job_status(self, client: AsyncClient, db_session) -> None:
        """List shows running job status correctly."""
        now = datetime.now(timezone.utc)
        job_run = ScheduledJobRunDB(
            job_name="check_dependabot_alerts",
            started_at=now,
            completed_at=None,
            status="running",
            projects_checked=3,
            alerts_sent=1,
        )
        db_session.add(job_run)
        await db_session.commit()

        response = await client.get("/api/admin/jobs/scheduled")
        assert response.status_code == 200
        data = response.json()

        dependabot_job = next(
            (j for j in data if j["name"] == "check_dependabot_alerts"), None
        )
        assert dependabot_job["last_run"]["status"] == "running"
        assert dependabot_job["last_run"]["completed_at"] is None
        assert dependabot_job["last_run"]["projects_checked"] == 3

    @pytest.mark.asyncio
    async def test_error_job_with_message(
        self, client: AsyncClient, db_session
    ) -> None:
        """List shows error job with error message."""
        now = datetime.now(timezone.utc)
        job_run = ScheduledJobRunDB(
            job_name="check_business_alerts",
            started_at=now,
            completed_at=now,
            status="error",
            projects_checked=0,
            alerts_sent=0,
            error_message="Slack not configured - missing bot token",
        )
        db_session.add(job_run)
        await db_session.commit()

        response = await client.get("/api/admin/jobs/scheduled")
        assert response.status_code == 200
        data = response.json()

        business_job = next(
            (j for j in data if j["name"] == "check_business_alerts"), None
        )
        assert business_job["last_run"]["status"] == "error"
        assert "Slack not configured" in business_job["last_run"]["error_message"]
