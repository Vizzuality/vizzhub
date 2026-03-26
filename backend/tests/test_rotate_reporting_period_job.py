"""Tests for Reporting Period Rotation scheduled job."""

from datetime import date
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.models.slack import ScheduledJobRunDB
from app.modules.tracker.models.reporting_period import (
    ReportingPeriodDB,
    ReportingPeriodStatus,
)
from app.worker.rotate_reporting_period import rotate_reporting_period


class TestDateGuard:
    """Tests for the day-of-month guard."""

    @pytest.mark.asyncio
    async def test_skips_on_non_15th(self, db_session: AsyncSession) -> None:
        """Job skips when not the 15th."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.rotate_reporting_period.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 14)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await rotate_reporting_period(ctx)

        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_runs_on_15th(self, db_session: AsyncSession) -> None:
        """Job runs when it's the 15th."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.rotate_reporting_period.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 15)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await rotate_reporting_period(ctx)

        assert result["status"] == "completed"


class TestRotateReportingPeriod:
    """Integration tests for rotate_reporting_period job."""

    @pytest_asyncio.fixture
    async def active_period(self, db_session: AsyncSession) -> ReportingPeriodDB:
        """Create an active reporting period for February 2026."""
        period = ReportingPeriodDB(
            date=date(2026, 2, 1),
            status=ReportingPeriodStatus.ACTIVE.value,
        )
        db_session.add(period)
        await db_session.commit()
        await db_session.refresh(period)
        return period

    @pytest.mark.asyncio
    async def test_finishes_active_and_creates_new(
        self, db_session: AsyncSession, active_period: ReportingPeriodDB
    ) -> None:
        """Job finishes current active period and creates + activates new one."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.rotate_reporting_period.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 15)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await rotate_reporting_period(ctx)

        assert result["status"] == "completed"

        await db_session.refresh(active_period)
        assert active_period.status == ReportingPeriodStatus.FINISHED.value

        new_period = (
            await db_session.execute(
                select(ReportingPeriodDB).where(
                    ReportingPeriodDB.date == date(2026, 3, 1)
                )
            )
        ).scalar_one_or_none()
        assert new_period is not None
        assert new_period.status == ReportingPeriodStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_creates_new_without_active(
        self, db_session: AsyncSession
    ) -> None:
        """Job creates and activates new period even when no active period exists."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.rotate_reporting_period.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 15)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await rotate_reporting_period(ctx)

        assert result["status"] == "completed"

        new_period = (
            await db_session.execute(
                select(ReportingPeriodDB).where(
                    ReportingPeriodDB.date == date(2026, 3, 1)
                )
            )
        ).scalar_one_or_none()
        assert new_period is not None
        assert new_period.status == ReportingPeriodStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_activates_existing_unstarted_period(
        self, db_session: AsyncSession, active_period: ReportingPeriodDB
    ) -> None:
        """Job activates existing unstarted period for current month instead of creating."""
        existing = ReportingPeriodDB(
            date=date(2026, 3, 1),
            status=ReportingPeriodStatus.UNSTARTED.value,
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        ctx = {"db": db_session}
        with patch(
            "app.worker.rotate_reporting_period.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 15)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await rotate_reporting_period(ctx)

        assert result["status"] == "completed"

        await db_session.refresh(existing)
        assert existing.status == ReportingPeriodStatus.ACTIVE.value

        await db_session.refresh(active_period)
        assert active_period.status == ReportingPeriodStatus.FINISHED.value

    @pytest.mark.asyncio
    async def test_noop_when_current_month_already_active(
        self, db_session: AsyncSession
    ) -> None:
        """Job does nothing if the current month's period is already active."""
        already_active = ReportingPeriodDB(
            date=date(2026, 3, 1),
            status=ReportingPeriodStatus.ACTIVE.value,
        )
        db_session.add(already_active)
        await db_session.commit()

        ctx = {"db": db_session}
        with patch(
            "app.worker.rotate_reporting_period.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 15)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await rotate_reporting_period(ctx)

        assert result["status"] == "completed"

        await db_session.refresh(already_active)
        assert already_active.status == ReportingPeriodStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_creates_job_run_record(
        self, db_session: AsyncSession
    ) -> None:
        """Job persists a ScheduledJobRunDB record."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.rotate_reporting_period.date"
        ) as mock_date:
            mock_date.today.return_value = date(2026, 3, 15)
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = await rotate_reporting_period(ctx)

        rows = (
            await db_session.execute(
                select(ScheduledJobRunDB).where(
                    ScheduledJobRunDB.job_name == "rotate_reporting_period"
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "completed"
        assert rows[0].id == result["job_run_id"]
