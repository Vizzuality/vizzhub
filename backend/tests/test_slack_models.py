"""Tests for Slack notification models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slack import (
    AlertCategory,
    AlertDefinitionDB,
    AlertNotificationDB,
    AlertSchedule,
    AlertSilenceDB,
    ChannelType,
    DependabotAlertTrackedDB,
    MessageTemplateDB,
    ScheduledJobRunDB,
    TemplateType,
)


class TestAlertDefinitionModel:
    """Tests for AlertDefinitionDB model."""

    def test_alert_definition_model_exists(self) -> None:
        """Test AlertDefinitionDB model has correct table name."""
        assert AlertDefinitionDB.__tablename__ == "alert_definitions"

    @pytest.mark.asyncio
    async def test_alert_definition_creation(self, db_session: AsyncSession) -> None:
        """Test creating an alert definition."""
        alert = AlertDefinitionDB(
            name="budget_variance_alert",
            description="Alert when budget variance exceeds threshold",
            category=AlertCategory.BUSINESS.value,
            channel_type=ChannelType.LEADERSHIP.value,
            schedule=AlertSchedule.DAILY_CHECK_MONTHLY_REPORT.value,
            is_enabled=True,
            config_json={"threshold": 10},
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        assert alert.id is not None
        assert alert.name == "budget_variance_alert"
        assert alert.description == "Alert when budget variance exceeds threshold"
        assert alert.category == AlertCategory.BUSINESS.value
        assert alert.channel_type == ChannelType.LEADERSHIP.value
        assert alert.schedule == AlertSchedule.DAILY_CHECK_MONTHLY_REPORT.value
        assert alert.is_enabled is True
        assert alert.config_json == {"threshold": 10}
        assert alert.created_at is not None
        assert alert.updated_at is not None

    @pytest.mark.asyncio
    async def test_alert_definition_unique_name(self, db_session: AsyncSession) -> None:
        """Test that alert definition name is unique."""
        alert1 = AlertDefinitionDB(
            name="duplicate_alert",
            category=AlertCategory.BUSINESS.value,
            channel_type=ChannelType.LEADERSHIP.value,
            schedule=AlertSchedule.DAILY.value,
        )
        alert2 = AlertDefinitionDB(
            name="duplicate_alert",
            category=AlertCategory.PROJECT.value,
            channel_type=ChannelType.PROJECT.value,
            schedule=AlertSchedule.DAILY.value,
        )

        db_session.add(alert1)
        await db_session.commit()

        db_session.add(alert2)
        with pytest.raises(IntegrityError):
            await db_session.commit()


class TestMessageTemplateModel:
    """Tests for MessageTemplateDB model."""

    def test_message_template_model_exists(self) -> None:
        """Test MessageTemplateDB model has correct table name."""
        assert MessageTemplateDB.__tablename__ == "message_templates"

    @pytest.mark.asyncio
    async def test_message_template_creation(self, db_session: AsyncSession) -> None:
        """Test creating a message template."""
        alert = AlertDefinitionDB(
            name="test_alert_for_template",
            category=AlertCategory.BUSINESS.value,
            channel_type=ChannelType.LEADERSHIP.value,
            schedule=AlertSchedule.DAILY.value,
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        template = MessageTemplateDB(
            alert_definition_id=alert.id,
            template_type=TemplateType.INITIAL.value,
            message_template="Budget alert: {project_name} has variance of {variance}%",
            is_active=True,
        )
        db_session.add(template)
        await db_session.commit()
        await db_session.refresh(template)

        assert template.id is not None
        assert template.alert_definition_id == alert.id
        assert template.template_type == TemplateType.INITIAL.value
        assert "Budget alert" in template.message_template
        assert template.is_active is True
        assert template.created_at is not None
        assert template.updated_at is not None

    @pytest.mark.asyncio
    async def test_message_template_cascade_delete(
        self, db_session: AsyncSession
    ) -> None:
        """Test that deleting alert definition cascades to templates."""
        alert = AlertDefinitionDB(
            name="cascade_test_alert",
            category=AlertCategory.PROJECT.value,
            channel_type=ChannelType.PROJECT.value,
            schedule=AlertSchedule.DAILY.value,
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        template = MessageTemplateDB(
            alert_definition_id=alert.id,
            template_type=TemplateType.REMINDER.value,
            message_template="Reminder message",
        )
        db_session.add(template)
        await db_session.commit()

        template_id = template.id

        await db_session.delete(alert)
        await db_session.commit()

        db_session.expire_all()

        deleted_template = await db_session.get(MessageTemplateDB, template_id)
        assert deleted_template is None


class TestEnums:
    """Tests for Slack-related enums."""

    def test_alert_category_values(self) -> None:
        """Test AlertCategory enum values."""
        assert AlertCategory.BUSINESS.value == "business"
        assert AlertCategory.PROJECT.value == "project"

    def test_channel_type_values(self) -> None:
        """Test ChannelType enum values."""
        assert ChannelType.LEADERSHIP.value == "leadership"
        assert ChannelType.PROJECT.value == "project"

    def test_alert_schedule_values(self) -> None:
        """Test AlertSchedule enum values."""
        assert (
            AlertSchedule.DAILY_CHECK_MONTHLY_REPORT.value
            == "daily_check_monthly_report"
        )
        assert AlertSchedule.DAILY.value == "daily"

    def test_template_type_values(self) -> None:
        """Test TemplateType enum values."""
        assert TemplateType.INITIAL.value == "initial"
        assert TemplateType.REMINDER.value == "reminder"
        assert TemplateType.ESCALATION.value == "escalation"


class TestAlertSilenceModel:
    """Tests for AlertSilenceDB model."""

    def test_alert_silence_model_exists(self) -> None:
        """Test AlertSilenceDB model has correct table name."""
        assert AlertSilenceDB.__tablename__ == "alert_silences"

    @pytest.mark.asyncio
    async def test_alert_silence_creation(self, db_session: AsyncSession) -> None:
        """Test creating an alert silence record."""
        from datetime import datetime, timezone, timedelta
        from uuid import uuid4
        from app.models.project import ProjectDB

        project = ProjectDB(
            id=uuid4(),
            name="Test Project for Silence",
            jira_project_key="SIL",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert = AlertDefinitionDB(
            name="silence_test_alert",
            category=AlertCategory.BUSINESS.value,
            channel_type=ChannelType.LEADERSHIP.value,
            schedule=AlertSchedule.DAILY.value,
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        silenced_until = datetime.now(timezone.utc) + timedelta(days=7)
        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            silenced_until=silenced_until,
            reason="Sprint planning week",
            created_by="test_user",
        )
        db_session.add(silence)
        await db_session.commit()
        await db_session.refresh(silence)

        assert silence.id is not None
        assert silence.project_id == project.id
        assert silence.alert_definition_id == alert.id
        assert silence.reason == "Sprint planning week"
        assert silence.created_by == "test_user"
        assert silence.created_at is not None

    @pytest.mark.asyncio
    async def test_alert_silence_without_alert_definition(
        self, db_session: AsyncSession
    ) -> None:
        """Test creating silence without specific alert definition (silences all)."""
        from uuid import uuid4
        from app.models.project import ProjectDB

        project = ProjectDB(
            id=uuid4(),
            name="Test Project for Global Silence",
            jira_project_key="GSL",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=None,
            reason="Project on hold",
        )
        db_session.add(silence)
        await db_session.commit()
        await db_session.refresh(silence)

        assert silence.id is not None
        assert silence.alert_definition_id is None


class TestAlertNotificationModel:
    """Tests for AlertNotificationDB model."""

    def test_alert_notification_model_exists(self) -> None:
        """Test AlertNotificationDB model has correct table name."""
        assert AlertNotificationDB.__tablename__ == "alert_notifications"

    @pytest.mark.asyncio
    async def test_alert_notification_creation(self, db_session: AsyncSession) -> None:
        """Test creating an alert notification log."""
        from uuid import uuid4
        from app.models.project import ProjectDB

        project = ProjectDB(
            id=uuid4(),
            name="Test Project for Notification",
            jira_project_key="NOT",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert = AlertDefinitionDB(
            name="notification_test_alert",
            category=AlertCategory.BUSINESS.value,
            channel_type=ChannelType.LEADERSHIP.value,
            schedule=AlertSchedule.DAILY.value,
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C123456789",
            message="Budget variance alert: Test Project exceeded threshold",
            status="sent",
            metadata_json={"variance": 15.5, "threshold": 10},
        )
        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)

        assert notification.id is not None
        assert notification.project_id == project.id
        assert notification.alert_definition_id == alert.id
        assert notification.channel_id == "C123456789"
        assert "Budget variance alert" in notification.message
        assert notification.status == "sent"
        assert notification.metadata_json["variance"] == pytest.approx(15.5)
        assert notification.sent_at is not None

    @pytest.mark.asyncio
    async def test_alert_notification_with_error(
        self, db_session: AsyncSession
    ) -> None:
        """Test creating a failed notification log."""
        from uuid import uuid4
        from app.models.project import ProjectDB

        project = ProjectDB(
            id=uuid4(),
            name="Test Project for Failed Notification",
            jira_project_key="FNT",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert = AlertDefinitionDB(
            name="failed_notification_test_alert",
            category=AlertCategory.PROJECT.value,
            channel_type=ChannelType.PROJECT.value,
            schedule=AlertSchedule.DAILY.value,
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert.id,
            channel_id="C987654321",
            message="Failed to send alert",
            status="failed",
            error_message="channel_not_found",
        )
        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)

        assert notification.status == "failed"
        assert notification.error_message == "channel_not_found"


class TestDependabotAlertTrackedModel:
    """Tests for DependabotAlertTrackedDB model."""

    def test_dependabot_alert_tracked_model_exists(self) -> None:
        """Test DependabotAlertTrackedDB model has correct table name."""
        assert DependabotAlertTrackedDB.__tablename__ == "dependabot_alerts_tracked"

    @pytest.mark.asyncio
    async def test_dependabot_alert_tracked_creation(
        self, db_session: AsyncSession
    ) -> None:
        """Test creating a tracked Dependabot alert."""
        from uuid import uuid4
        from app.models.project import ProjectDB

        project = ProjectDB(
            id=uuid4(),
            name="Test Project for Dependabot",
            jira_project_key="DEP",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        tracked_alert = DependabotAlertTrackedDB(
            project_id=project.id,
            github_alert_id=12345,
            package_name="lodash",
            severity="high",
            cve_id="CVE-2021-23337",
        )
        db_session.add(tracked_alert)
        await db_session.commit()
        await db_session.refresh(tracked_alert)

        assert tracked_alert.id is not None
        assert tracked_alert.project_id == project.id
        assert tracked_alert.github_alert_id == 12345
        assert tracked_alert.package_name == "lodash"
        assert tracked_alert.severity == "high"
        assert tracked_alert.cve_id == "CVE-2021-23337"
        assert tracked_alert.first_seen_at is not None
        assert tracked_alert.last_notified_at is None
        assert tracked_alert.resolved_at is None

    @pytest.mark.asyncio
    async def test_dependabot_alert_tracked_resolved(
        self, db_session: AsyncSession
    ) -> None:
        """Test marking a Dependabot alert as resolved."""
        from datetime import datetime, timezone
        from uuid import uuid4
        from app.models.project import ProjectDB

        project = ProjectDB(
            id=uuid4(),
            name="Test Project for Resolved Dependabot",
            jira_project_key="RDP",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        tracked_alert = DependabotAlertTrackedDB(
            project_id=project.id,
            github_alert_id=67890,
            package_name="axios",
            severity="critical",
        )
        db_session.add(tracked_alert)
        await db_session.commit()
        await db_session.refresh(tracked_alert)

        tracked_alert.resolved_at = datetime.now(timezone.utc)
        tracked_alert.last_notified_at = datetime.now(timezone.utc)
        await db_session.commit()
        await db_session.refresh(tracked_alert)

        assert tracked_alert.resolved_at is not None
        assert tracked_alert.last_notified_at is not None


class TestScheduledJobRunModel:
    """Tests for ScheduledJobRunDB model."""

    def test_scheduled_job_run_model_exists(self) -> None:
        """Test ScheduledJobRunDB model has correct table name."""
        assert ScheduledJobRunDB.__tablename__ == "scheduled_job_runs"

    @pytest.mark.asyncio
    async def test_scheduled_job_run_creation(self, db_session: AsyncSession) -> None:
        """Test creating a scheduled job run record."""
        job_run = ScheduledJobRunDB(
            job_name="daily_business_alerts_check",
            status="running",
            projects_checked=0,
            alerts_sent=0,
        )
        db_session.add(job_run)
        await db_session.commit()
        await db_session.refresh(job_run)

        assert job_run.id is not None
        assert job_run.job_name == "daily_business_alerts_check"
        assert job_run.started_at is not None
        assert job_run.completed_at is None
        assert job_run.status == "running"
        assert job_run.projects_checked == 0
        assert job_run.alerts_sent == 0
        assert job_run.error_message is None

    @pytest.mark.asyncio
    async def test_scheduled_job_run_completed(self, db_session: AsyncSession) -> None:
        """Test completing a scheduled job run."""
        from datetime import datetime, timezone

        job_run = ScheduledJobRunDB(
            job_name="daily_dependabot_check",
            status="running",
        )
        db_session.add(job_run)
        await db_session.commit()
        await db_session.refresh(job_run)

        job_run.completed_at = datetime.now(timezone.utc)
        job_run.status = "completed"
        job_run.projects_checked = 10
        job_run.alerts_sent = 3
        await db_session.commit()
        await db_session.refresh(job_run)

        assert job_run.completed_at is not None
        assert job_run.status == "completed"
        assert job_run.projects_checked == 10
        assert job_run.alerts_sent == 3

    @pytest.mark.asyncio
    async def test_scheduled_job_run_failed(self, db_session: AsyncSession) -> None:
        """Test a failed scheduled job run."""
        from datetime import datetime, timezone

        job_run = ScheduledJobRunDB(
            job_name="daily_business_alerts_check",
            status="running",
        )
        db_session.add(job_run)
        await db_session.commit()
        await db_session.refresh(job_run)

        job_run.completed_at = datetime.now(timezone.utc)
        job_run.status = "failed"
        job_run.error_message = "Database connection timeout"
        await db_session.commit()
        await db_session.refresh(job_run)

        assert job_run.status == "failed"
        assert job_run.error_message == "Database connection timeout"
