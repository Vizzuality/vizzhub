"""Tests for Report Confirmation Reminder scheduled job."""

from datetime import date
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.oauth import OAuthTokenDB
from app.core.models.user import UserDB
from app.core.token_encryption import encrypt_token
from app.modules.notifications.models.slack import ScheduledJobRunDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.worker.report_confirmation_reminder import (
    _is_reminder_window,
    send_report_confirmation_reminder,
)


class TestIsReminderWindow:
    """Tests for the reminder window date check."""

    def test_day_2_weekday(self) -> None:
        """2026-03-02 is Monday — in window."""
        assert _is_reminder_window(date(2026, 3, 2)) is True

    def test_day_12_weekday(self) -> None:
        """2026-03-12 is Thursday — in window."""
        assert _is_reminder_window(date(2026, 3, 12)) is True

    def test_day_1_excluded(self) -> None:
        """Day 1 is before the window."""
        assert _is_reminder_window(date(2026, 3, 1)) is False

    def test_day_13_excluded(self) -> None:
        """Day 13 is after the window."""
        assert _is_reminder_window(date(2026, 3, 13)) is False

    def test_saturday_excluded(self) -> None:
        """2026-03-07 is Saturday — weekend excluded."""
        assert _is_reminder_window(date(2026, 3, 7)) is False

    def test_sunday_excluded(self) -> None:
        """2026-03-08 is Sunday — weekend excluded."""
        assert _is_reminder_window(date(2026, 3, 8)) is False

    def test_day_5_friday(self) -> None:
        """2026-03-06 is Friday — in window."""
        assert _is_reminder_window(date(2026, 3, 6)) is True


class TestSendReportConfirmationReminder:
    """Integration tests for send_report_confirmation_reminder job."""

    @pytest_asyncio.fixture
    async def setup_slack_token(self, db_session: AsyncSession) -> None:
        """Set up Slack bot token."""
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
        db_session.add(token)
        await db_session.commit()

    @pytest_asyncio.fixture
    async def active_period(self, db_session: AsyncSession) -> ReportingPeriodDB:
        """Create an active reporting period."""
        period = ReportingPeriodDB(
            date=date(2026, 3, 1),
            status="active",
        )
        db_session.add(period)
        await db_session.commit()
        await db_session.refresh(period)
        return period

    @pytest_asyncio.fixture
    async def user_with_slack(self, db_session: AsyncSession) -> UserDB:
        """Create an active user with Slack ID and project reporting."""
        user = UserDB(
            id=uuid4(),
            email="test@example.com",
            active=True,
            requires_project_reporting=True,
            slack_user_id="U_TEST_USER",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_skips_outside_window(
        self, db_session: AsyncSession
    ) -> None:
        """Job skips when outside the reminder window."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.report_confirmation_reminder._is_reminder_window",
            return_value=False,
        ):
            result = await send_report_confirmation_reminder(ctx)

        assert result["status"] == "skipped"
        assert result["alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_error_no_bot_token(
        self, db_session: AsyncSession
    ) -> None:
        """Job errors when Slack bot token missing."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.report_confirmation_reminder._is_reminder_window",
            return_value=True,
        ):
            result = await send_report_confirmation_reminder(ctx)

        assert result["status"] == "error"
        assert "bot token" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_error_no_active_period(
        self, db_session: AsyncSession, setup_slack_token: None
    ) -> None:
        """Job errors when no active reporting period."""
        ctx = {"db": db_session}
        with patch(
            "app.worker.report_confirmation_reminder._is_reminder_window",
            return_value=True,
        ):
            result = await send_report_confirmation_reminder(ctx)

        assert result["status"] == "error"
        assert "active reporting period" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_sends_dm_to_unconfirmed_user(
        self,
        db_session: AsyncSession,
        setup_slack_token: None,
        active_period: ReportingPeriodDB,
        user_with_slack: UserDB,
    ) -> None:
        """Job sends DM to user who hasn't confirmed."""
        ctx = {"db": db_session}
        mock_response = {"ok": True, "ts": "123"}

        with (
            patch(
                "app.worker.report_confirmation_reminder._is_reminder_window",
                return_value=True,
            ),
            patch(
                "app.worker.report_confirmation_reminder.SlackService.send_message",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_send,
        ):
            result = await send_report_confirmation_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 1
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][1] == "U_TEST_USER"
        assert "March 2026" in call_args[0][2]

    @pytest.mark.asyncio
    async def test_skips_confirmed_user(
        self,
        db_session: AsyncSession,
        setup_slack_token: None,
        active_period: ReportingPeriodDB,
        user_with_slack: UserDB,
    ) -> None:
        """Job skips user who has confirmed report."""
        report = ReportDB(
            user_id=user_with_slack.id,
            reporting_period_id=active_period.id,
            estimated=False,
        )
        db_session.add(report)
        await db_session.commit()

        ctx = {"db": db_session}
        with (
            patch(
                "app.worker.report_confirmation_reminder._is_reminder_window",
                return_value=True,
            ),
            patch(
                "app.worker.report_confirmation_reminder.SlackService.send_message",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            result = await send_report_confirmation_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_to_estimated_user(
        self,
        db_session: AsyncSession,
        setup_slack_token: None,
        active_period: ReportingPeriodDB,
        user_with_slack: UserDB,
    ) -> None:
        """Job sends DM to user with estimated (unconfirmed) report."""
        report = ReportDB(
            user_id=user_with_slack.id,
            reporting_period_id=active_period.id,
            estimated=True,
        )
        db_session.add(report)
        await db_session.commit()

        ctx = {"db": db_session}
        mock_response = {"ok": True, "ts": "123"}

        with (
            patch(
                "app.worker.report_confirmation_reminder._is_reminder_window",
                return_value=True,
            ),
            patch(
                "app.worker.report_confirmation_reminder.SlackService.send_message",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_send,
        ):
            result = await send_report_confirmation_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 1
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_user_without_slack(
        self,
        db_session: AsyncSession,
        setup_slack_token: None,
        active_period: ReportingPeriodDB,
    ) -> None:
        """Job skips users without Slack ID."""
        user = UserDB(
            id=uuid4(),
            email="noslack@example.com",
            active=True,
            requires_project_reporting=True,
            slack_user_id=None,
        )
        db_session.add(user)
        await db_session.commit()

        ctx = {"db": db_session}
        with (
            patch(
                "app.worker.report_confirmation_reminder._is_reminder_window",
                return_value=True,
            ),
            patch(
                "app.worker.report_confirmation_reminder.SlackService.send_message",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            result = await send_report_confirmation_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_inactive_user(
        self,
        db_session: AsyncSession,
        setup_slack_token: None,
        active_period: ReportingPeriodDB,
    ) -> None:
        """Job skips inactive users."""
        user = UserDB(
            id=uuid4(),
            email="inactive@example.com",
            active=False,
            requires_project_reporting=True,
            slack_user_id="U_INACTIVE",
        )
        db_session.add(user)
        await db_session.commit()

        ctx = {"db": db_session}
        with (
            patch(
                "app.worker.report_confirmation_reminder._is_reminder_window",
                return_value=True,
            ),
            patch(
                "app.worker.report_confirmation_reminder.SlackService.send_message",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            result = await send_report_confirmation_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 0
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_scheduled_job_run(
        self,
        db_session: AsyncSession,
        setup_slack_token: None,
        active_period: ReportingPeriodDB,
        user_with_slack: UserDB,
    ) -> None:
        """Job persists a ScheduledJobRunDB record."""
        ctx = {"db": db_session}
        mock_response = {"ok": True, "ts": "123"}

        with (
            patch(
                "app.worker.report_confirmation_reminder._is_reminder_window",
                return_value=True,
            ),
            patch(
                "app.worker.report_confirmation_reminder.SlackService.send_message",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            result = await send_report_confirmation_reminder(ctx)

        rows = (
            await db_session.execute(
                sa_select(ScheduledJobRunDB).where(
                    ScheduledJobRunDB.job_name == "send_report_confirmation_reminder"
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "completed"
        assert rows[0].id == result["job_run_id"]
