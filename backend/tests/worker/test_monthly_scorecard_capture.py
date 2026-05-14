"""Tests for monthly_scorecard_capture worker job recovery paths."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models.slack import ScheduledJobRunDB
from app.worker.monthly_scorecard_capture import monthly_scorecard_capture


async def _latest_run(db: AsyncSession) -> ScheduledJobRunDB:
    """Return the most recent monthly_scorecard_capture run row."""
    result = await db.execute(
        select(ScheduledJobRunDB)
        .where(ScheduledJobRunDB.job_name == "monthly_scorecard_capture")
        .order_by(ScheduledJobRunDB.started_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    assert row is not None, "expected a run row to exist"
    return row


@pytest.mark.asyncio
async def test_job_failure_marks_run_as_error_not_running(
    db_session: AsyncSession, scoring_config
) -> None:
    """When the job body raises, the run row must end up as 'error', not stuck in 'running'.

    Regression: a NumericValueOutOfRangeError on a single project poisoned the
    SQLAlchemy session with PendingRollbackError. The outer except then tried to
    commit the status update on the same broken session, which raised again — so
    the row stayed in 'running' forever. The fix rolls back before issuing a raw
    UPDATE for the status.
    """
    ctx = {"db": db_session, "score_cache": None}

    # Force the project loader to raise so the outer except path runs without
    # depending on Jira/GitHub fixtures.
    with patch(
        "app.worker.monthly_scorecard_capture._get_scorecard_projects",
        new=AsyncMock(side_effect=RuntimeError("simulated collector failure")),
    ):
        result = await monthly_scorecard_capture(ctx)

    assert result["status"] == "error"
    assert "simulated collector failure" in result["error"]

    row = await _latest_run(db_session)
    assert row.status == "error"
    assert row.completed_at is not None
    assert "simulated collector failure" in (row.error_message or "")


@pytest.mark.asyncio
async def test_job_success_marks_run_as_completed(
    db_session: AsyncSession, scoring_config
) -> None:
    """Happy path: zero projects → run finalises as 'completed' with counters at 0."""
    ctx = {"db": db_session, "score_cache": None}

    with patch(
        "app.worker.monthly_scorecard_capture._get_scorecard_projects",
        new=AsyncMock(return_value=[]),
    ):
        result = await monthly_scorecard_capture(ctx)

    assert result["status"] == "completed"
    assert result["captured"] == 0

    row = await _latest_run(db_session)
    assert row.status == "completed"
    assert row.projects_checked == 0
    assert row.alerts_sent == 0
    assert row.completed_at is not None


@pytest.mark.asyncio
async def test_per_project_failure_does_not_poison_outer_commit(
    db_session: AsyncSession, scoring_config
) -> None:
    """A failing project triggers rollback per iteration; the outer commit still finalises.

    Regression: without the inner `await db.rollback()`, the SQLAlchemy session
    is left in PendingRollbackError after a bad upsert, and the final commit
    that flips status='completed' fails — leaving the row stuck in 'running'.
    """

    class _Proj:
        def __init__(self, name: str) -> None:
            self.id = "00000000-0000-0000-0000-000000000000"
            self.name = name
            self.budget = None
            self.start_date = None
            self.end_date = None

    ctx = {"db": db_session, "score_cache": None}

    with (
        patch(
            "app.worker.monthly_scorecard_capture._get_scorecard_projects",
            new=AsyncMock(return_value=[_Proj("FailingProject")]),
        ),
        patch(
            "app.worker.monthly_scorecard_capture.MetricsService.get_manual_fields_for_historical_capture",
            new=AsyncMock(side_effect=RuntimeError("simulated upsert overflow")),
        ),
    ):
        result = await monthly_scorecard_capture(ctx)

    assert result["status"] == "completed"
    assert result["captured"] == 0
    assert result["errors"] == 1
    assert result["error_details"][0]["project"] == "FailingProject"

    row = await _latest_run(db_session)
    assert row.status == "completed"
    assert row.projects_checked == 1
    assert row.alerts_sent == 0
