"""Tests for worker metrics module."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.worker.metrics import arq_jobs_total, arq_job_duration_seconds


class TestWorkerMetrics:
    """Verify Prometheus metrics are defined correctly."""

    def test_arq_jobs_total_is_counter(self) -> None:
        assert arq_jobs_total._type == "counter"

    def test_arq_job_duration_is_histogram(self) -> None:
        assert arq_job_duration_seconds._type == "histogram"

    def test_counter_can_increment(self) -> None:
        before = arq_jobs_total._value.get()
        arq_jobs_total.inc()
        after = arq_jobs_total._value.get()
        assert after == before + 1

    def test_histogram_can_observe(self) -> None:
        arq_job_duration_seconds.observe(0.5)


class TestOnJobHooksMetrics:
    """Verify on_job_start/on_job_end record metrics."""

    @pytest.mark.asyncio
    async def test_on_job_end_increments_counter_and_records_duration(self) -> None:
        from app.worker.settings import on_job_start, on_job_end

        before_count = arq_jobs_total._value.get()

        mock_db = AsyncMock()
        mock_session_maker = MagicMock(return_value=mock_db)

        ctx: dict = {
            "db_session_maker": mock_session_maker,
        }
        await on_job_start(ctx)
        assert "_job_start_time" in ctx

        await on_job_end(ctx)

        after_count = arq_jobs_total._value.get()
        assert after_count == before_count + 1
        mock_db.close.assert_awaited_once()
