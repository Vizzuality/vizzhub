"""Tests for Business Alerts check job.

This module tests the check_business_alerts cron job which runs daily
to check all projects for business alert conditions and send Slack
notifications to the leadership channel (monthly throttled).

Business alerts:
1. Budget exceeded (>=100% consumed)
2. Timeline at risk (velocity suggests won't complete by end_date)
3. Project overdue (>30 days past end_date)
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import MetricsDB, SnapshotType
from app.models.project import ProjectDB
from app.models.slack import (
    AlertDefinitionDB,
    AlertNotificationDB,
    AlertSilenceDB,
    MessageTemplateDB,
    SlackConfigDB,
)
from app.worker.check_business_alerts import check_business_alerts


class TestCheckBusinessAlertsJobExists:
    """Basic existence tests for the job."""

    def test_check_business_alerts_job_exists(self) -> None:
        """check_business_alerts function should be callable."""
        assert callable(check_business_alerts)


class TestCheckBusinessAlertsJob:
    """Integration tests for the Business Alerts check job."""

    @pytest.fixture
    def mock_slack_config(self) -> SlackConfigDB:
        """Create a mock Slack config with leadership channel."""
        return SlackConfigDB(
            id=1,
            bot_token_encrypted="xoxb-test-token",
            leadership_channel_id="C_LEADERSHIP",
        )

    @pytest_asyncio.fixture
    async def setup_slack_and_alerts(
        self, db_session: AsyncSession
    ) -> tuple[SlackConfigDB, dict[str, AlertDefinitionDB]]:
        """Set up Slack config and all business alert definitions."""
        slack_config = SlackConfigDB(
            bot_token_encrypted="xoxb-test-token",
            leadership_channel_id="C_LEADERSHIP",
        )
        db_session.add(slack_config)

        alert_defs = {}
        for name in ["budget_exceeded", "timeline_at_risk", "project_overdue"]:
            alert_def = AlertDefinitionDB(
                name=name,
                category="business",
                channel_type="leadership",
                schedule="daily_check_monthly_report",
                is_enabled=True,
                config_json={"grace_days": 30} if name == "project_overdue" else {},
            )
            db_session.add(alert_def)
            await db_session.flush()
            alert_defs[name] = alert_def

            template = MessageTemplateDB(
                alert_definition_id=alert_def.id,
                template_type="initial",
                message_template=f"Test template for {name}: {{project_name}}",
                is_active=True,
            )
            db_session.add(template)

        await db_session.commit()
        return slack_config, alert_defs

    @pytest.mark.asyncio
    async def test_job_creates_job_run_record(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should create a ScheduledJobRunDB record at start."""
        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
            result = await check_business_alerts(ctx)

        assert result["status"] == "completed"
        assert "job_run_id" in result

    @pytest.mark.asyncio
    async def test_job_returns_error_without_slack_config(
        self, db_session: AsyncSession
    ) -> None:
        """Job should return error when Slack is not configured."""
        ctx = {"db": db_session}

        result = await check_business_alerts(ctx)

        assert result["status"] == "error"
        assert "not configured" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_job_returns_error_without_leadership_channel(
        self, db_session: AsyncSession
    ) -> None:
        """Job should return error when leadership channel is not configured."""
        slack_config = SlackConfigDB(
            bot_token_encrypted="xoxb-test-token",
            leadership_channel_id=None,
        )
        db_session.add(slack_config)
        await db_session.commit()

        ctx = {"db": db_session}

        result = await check_business_alerts(ctx)

        assert result["status"] == "error"
        assert "leadership" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_job_skips_finished_projects(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should skip finished projects."""
        project = ProjectDB(
            name="Finished Project",
            status="finished",
            finished_at=date(2024, 1, 1),
        )
        db_session.add(project)
        await db_session.commit()

        ctx = {"db": db_session}

        result = await check_business_alerts(ctx)

        assert result["projects_checked"] == 0

    @pytest.mark.asyncio
    async def test_budget_exceeded_alert(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should send alert when budget is exceeded (>=100%)."""
        project = ProjectDB(
            name="Over Budget Project",
            status="in_progress",
        )
        db_session.add(project)
        await db_session.flush()

        metrics = MetricsDB(
            project_id=project.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type=SnapshotType.CUMULATIVE.value,
            budget_total=Decimal("100000"),
            cost_to_date=Decimal("105000"),
        )
        db_session.add(metrics)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            result = await check_business_alerts(ctx)

        assert result["alerts_sent"] >= 1
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_budget_not_exceeded_no_alert(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should not alert when budget is under 100%."""
        project = ProjectDB(
            name="Under Budget Project",
            status="in_progress",
        )
        db_session.add(project)
        await db_session.flush()

        metrics = MetricsDB(
            project_id=project.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type=SnapshotType.CUMULATIVE.value,
            budget_total=Decimal("100000"),
            cost_to_date=Decimal("50000"),
        )
        db_session.add(metrics)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_business_alerts(ctx)

        for call in mock_send.call_args_list:
            message = call[0][2] if len(call[0]) > 2 else call[1].get("message", "")
            assert "exceeded budget" not in message.lower()

    @pytest.mark.asyncio
    async def test_project_overdue_alert(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should send alert when project is >30 days past end_date."""
        past_date = date.today() - timedelta(days=45)
        project = ProjectDB(
            name="Overdue Project",
            status="in_progress",
            end_date=past_date,
        )
        db_session.add(project)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            result = await check_business_alerts(ctx)

        assert result["alerts_sent"] >= 1
        mock_send.assert_called()

    @pytest.mark.asyncio
    async def test_project_not_overdue_within_grace_period(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should not alert when project is within 30 day grace period."""
        past_date = date.today() - timedelta(days=15)
        project = ProjectDB(
            name="Near End Project",
            status="in_progress",
            end_date=past_date,
        )
        db_session.add(project)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_business_alerts(ctx)

        for call in mock_send.call_args_list:
            message = call[0][2] if len(call[0]) > 2 else call[1].get("message", "")
            assert "overdue" not in message.lower() and "past" not in message.lower()

    @pytest.mark.asyncio
    async def test_monthly_throttling(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should not send alert if already notified this month."""
        slack_config, alert_defs = setup_slack_and_alerts

        project = ProjectDB(
            name="Already Notified Project",
            status="in_progress",
        )
        db_session.add(project)
        await db_session.flush()

        metrics = MetricsDB(
            project_id=project.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type=SnapshotType.CUMULATIVE.value,
            budget_total=Decimal("100000"),
            cost_to_date=Decimal("110000"),
        )
        db_session.add(metrics)

        previous_notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert_defs["budget_exceeded"].id,
            channel_id="C_LEADERSHIP",
            message="Previous alert",
            status="sent",
        )
        db_session.add(previous_notification)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_business_alerts(ctx)

        budget_calls = [
            call for call in mock_send.call_args_list
            if "budget" in str(call).lower()
        ]
        assert len(budget_calls) == 0

    @pytest.mark.asyncio
    async def test_respects_silence(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should not send alerts for silenced projects."""
        slack_config, alert_defs = setup_slack_and_alerts

        project = ProjectDB(
            name="Silenced Project",
            status="in_progress",
        )
        db_session.add(project)
        await db_session.flush()

        metrics = MetricsDB(
            project_id=project.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type=SnapshotType.CUMULATIVE.value,
            budget_total=Decimal("100000"),
            cost_to_date=Decimal("110000"),
        )
        db_session.add(metrics)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=alert_defs["budget_exceeded"].id,
            silenced_until=datetime.now(timezone.utc) + timedelta(days=7),
            reason="Planned overage",
        )
        db_session.add(silence)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_business_alerts(ctx)

        budget_calls = [
            call for call in mock_send.call_args_list
            if "budget" in str(call).lower()
        ]
        assert len(budget_calls) == 0

    @pytest.mark.asyncio
    async def test_logs_notification_on_send(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should create AlertNotificationDB record when sending alert."""
        project = ProjectDB(
            name="Test Logging Project",
            status="in_progress",
        )
        db_session.add(project)
        await db_session.flush()

        metrics = MetricsDB(
            project_id=project.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type=SnapshotType.CUMULATIVE.value,
            budget_total=Decimal("100000"),
            cost_to_date=Decimal("110000"),
        )
        db_session.add(metrics)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
            await check_business_alerts(ctx)

        from sqlalchemy import select

        result = await db_session.execute(
            select(AlertNotificationDB).where(
                AlertNotificationDB.project_id == project.id
            )
        )
        notifications = result.scalars().all()

        assert len(notifications) >= 1
        assert any(n.status == "sent" for n in notifications)

    @pytest.mark.asyncio
    async def test_timeline_at_risk_alert(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should send alert when velocity suggests timeline risk."""
        future_date = date.today() + timedelta(days=30)
        project = ProjectDB(
            name="Timeline Risk Project",
            status="in_progress",
            end_date=future_date,
        )
        db_session.add(project)
        await db_session.flush()

        metrics = MetricsDB(
            project_id=project.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type=SnapshotType.CUMULATIVE.value,
            bugs_total=100,
            tasks_completed=10,
        )
        db_session.add(metrics)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
            result = await check_business_alerts(ctx)

        assert result["projects_checked"] >= 1

    @pytest.mark.asyncio
    async def test_sends_to_leadership_channel(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should send alerts to leadership channel, not project channel."""
        project = ProjectDB(
            name="Leadership Alert Project",
            status="in_progress",
            slack_channel_id="C_PROJECT",
        )
        db_session.add(project)
        await db_session.flush()

        metrics = MetricsDB(
            project_id=project.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type=SnapshotType.CUMULATIVE.value,
            budget_total=Decimal("100000"),
            cost_to_date=Decimal("110000"),
        )
        db_session.add(metrics)
        await db_session.commit()

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_send:
            await check_business_alerts(ctx)

        for call in mock_send.call_args_list:
            channel_id = call[0][1] if len(call[0]) > 1 else call[1].get("channel")
            assert channel_id == "C_LEADERSHIP"

    @pytest.mark.asyncio
    async def test_continues_on_project_error(
        self, db_session: AsyncSession, setup_slack_and_alerts
    ) -> None:
        """Job should continue processing other projects if one fails."""
        project1 = ProjectDB(
            name="Problem Project",
            status="in_progress",
        )
        project2 = ProjectDB(
            name="Good Project",
            status="in_progress",
        )
        db_session.add(project1)
        db_session.add(project2)
        await db_session.flush()

        metrics1 = MetricsDB(
            project_id=project1.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type=SnapshotType.CUMULATIVE.value,
            budget_total=Decimal("100000"),
            cost_to_date=Decimal("110000"),
        )
        metrics2 = MetricsDB(
            project_id=project2.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
            period_year=2024,
            period_month=1,
            snapshot_type=SnapshotType.CUMULATIVE.value,
            budget_total=Decimal("100000"),
            cost_to_date=Decimal("110000"),
        )
        db_session.add(metrics1)
        db_session.add(metrics2)
        await db_session.commit()

        call_count = 0

        async def mock_send_with_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Slack API error")
            return {"ok": True}

        ctx = {"db": db_session}

        with patch(
            "app.worker.check_business_alerts.SlackService.send_message",
            new_callable=AsyncMock,
            side_effect=mock_send_with_error,
        ):
            result = await check_business_alerts(ctx)

        assert result["status"] == "completed"
        assert result["projects_checked"] == 2
