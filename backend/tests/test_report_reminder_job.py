"""Tests for Report Reminder scheduled job."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.integration_setting import IntegrationSettingDB
from app.core.models.oauth import OAuthTokenDB
from app.core.token_encryption import encrypt_token
from app.modules.scorecard.models.slack import ScheduledJobRunDB
from app.worker.report_reminder import _is_last_business_day, send_monthly_report_reminder, REPORT_REMINDER_MESSAGE


class TestIsLastBusinessDay:
    """Tests for last-business-day-of-month logic."""

    def test_last_day_is_weekday(self) -> None:
        assert _is_last_business_day(date(2026, 3, 31)) is True

    def test_last_day_is_saturday(self) -> None:
        assert _is_last_business_day(date(2026, 1, 30)) is True
        assert _is_last_business_day(date(2026, 1, 31)) is False

    def test_last_day_is_sunday(self) -> None:
        assert _is_last_business_day(date(2026, 5, 29)) is True
        assert _is_last_business_day(date(2026, 5, 31)) is False
        assert _is_last_business_day(date(2026, 5, 30)) is False

    def test_february_non_leap(self) -> None:
        assert _is_last_business_day(date(2026, 2, 27)) is True
        assert _is_last_business_day(date(2026, 2, 28)) is False

    def test_february_leap_year(self) -> None:
        assert _is_last_business_day(date(2028, 2, 29)) is True

    def test_mid_month_is_false(self) -> None:
        assert _is_last_business_day(date(2026, 3, 15)) is False

    def test_december(self) -> None:
        assert _is_last_business_day(date(2026, 12, 31)) is True


class TestSendReportReminder:
    """Integration tests for send_monthly_report_reminder job."""

    @pytest_asyncio.fixture
    async def setup_slack(self, db_session: AsyncSession) -> None:
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
        db_session.add(token)

        setting = IntegrationSettingDB(
            provider="slack",
            key="tracker_reminder_channel_id",
            value="C_TRACKER_REMIND",
        )
        db_session.add(setting)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_skips_when_not_last_business_day(
        self, db_session: AsyncSession, setup_slack: None
    ) -> None:
        ctx = {"db": db_session}
        with patch(
            "app.worker.report_reminder._is_last_business_day", return_value=False
        ):
            result = await send_monthly_report_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_sends_on_last_business_day(
        self, db_session: AsyncSession, setup_slack: None
    ) -> None:
        ctx = {"db": db_session}
        mock_response = {"ok": True, "ts": "1234567890.123456"}

        with (
            patch(
                "app.worker.report_reminder._is_last_business_day", return_value=True
            ),
            patch(
                "app.worker.report_reminder.SlackService.send_message",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_send,
        ):
            result = await send_monthly_report_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 1
        mock_send.assert_called_once_with(
            "xoxb-test-token", "C_TRACKER_REMIND", REPORT_REMINDER_MESSAGE
        )

    @pytest.mark.asyncio
    async def test_error_when_no_bot_token(
        self, db_session: AsyncSession
    ) -> None:
        ctx = {"db": db_session}
        with patch(
            "app.worker.report_reminder._is_last_business_day", return_value=True
        ):
            result = await send_monthly_report_reminder(ctx)

        assert result["status"] == "error"
        assert "bot token" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_error_when_no_channel(
        self, db_session: AsyncSession
    ) -> None:
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
        db_session.add(token)
        await db_session.commit()

        ctx = {"db": db_session}
        with patch(
            "app.worker.report_reminder._is_last_business_day", return_value=True
        ):
            result = await send_monthly_report_reminder(ctx)

        assert result["status"] == "error"
        assert "channel" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_handles_slack_failure(
        self, db_session: AsyncSession, setup_slack: None
    ) -> None:
        ctx = {"db": db_session}
        mock_response = {"ok": False, "error": "channel_not_found"}

        with (
            patch(
                "app.worker.report_reminder._is_last_business_day", return_value=True
            ),
            patch(
                "app.worker.report_reminder.SlackService.send_message",
                new_callable=AsyncMock,
                return_value=mock_response,
            ),
        ):
            result = await send_monthly_report_reminder(ctx)

        assert result["status"] == "completed"
        assert result["alerts_sent"] == 0

    @pytest.mark.asyncio
    async def test_creates_scheduled_job_run(
        self, db_session: AsyncSession, setup_slack: None
    ) -> None:
        ctx = {"db": db_session}
        with patch(
            "app.worker.report_reminder._is_last_business_day", return_value=False
        ):
            result = await send_monthly_report_reminder(ctx)

        from sqlalchemy import select

        rows = (
            await db_session.execute(
                select(ScheduledJobRunDB).where(
                    ScheduledJobRunDB.job_name == "send_monthly_report_reminder"
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == "completed"
        assert rows[0].id == result["job_run_id"]
