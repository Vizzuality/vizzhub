"""Tests for AlertService.

This module tests the AlertService which handles alert management
including template rendering, silence checking, notification throttling,
and notification logging.
"""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slack import (
    AlertDefinitionDB,
    AlertNotificationDB,
    AlertSilenceDB,
    MessageTemplateDB,
)
from app.core.models.project import ProjectDB
from app.services.alert_service import AlertService


class TestRenderTemplate:
    """Test template rendering functionality."""

    def test_render_template_basic(self) -> None:
        """render_template should replace placeholders with context values."""
        template = "Project {project_name} has {budget_percent}% budget used"
        context = {"project_name": "Test Project", "budget_percent": 85}

        result = AlertService.render_template(template, context)

        assert result == "Project Test Project has 85% budget used"

    def test_render_template_missing_placeholder(self) -> None:
        """render_template should preserve missing placeholders."""
        template = "Project {project_name} has {missing_field}"
        context = {"project_name": "Test Project"}

        result = AlertService.render_template(template, context)

        assert "{missing_field}" in result
        assert "Test Project" in result

    def test_render_template_all_placeholders(self) -> None:
        """render_template should replace all placeholders correctly."""
        template = ":warning: *{project_name}* has exceeded budget ({budget_percent}% consumed)"
        context = {"project_name": "MyApp", "budget_percent": "105.3"}

        result = AlertService.render_template(template, context)

        assert result == ":warning: *MyApp* has exceeded budget (105.3% consumed)"

    def test_render_template_numeric_values(self) -> None:
        """render_template should convert numeric values to strings."""
        template = "Score: {score} points, Rating: {rating}"
        context = {"score": 100, "rating": 4.5}

        result = AlertService.render_template(template, context)

        assert result == "Score: 100 points, Rating: 4.5"

    def test_render_template_empty_context(self) -> None:
        """render_template should preserve all placeholders with empty context."""
        template = "Hello {name}, welcome to {location}"
        context: dict = {}

        result = AlertService.render_template(template, context)

        assert result == "Hello {name}, welcome to {location}"

    def test_render_template_no_placeholders(self) -> None:
        """render_template should return template unchanged if no placeholders."""
        template = "This is a static message"
        context = {"unused": "value"}

        result = AlertService.render_template(template, context)

        assert result == "This is a static message"

    def test_render_template_repeated_placeholder(self) -> None:
        """render_template should replace repeated placeholders."""
        template = "{name} is great, {name} is awesome"
        context = {"name": "Claude"}

        result = AlertService.render_template(template, context)

        assert result == "Claude is great, Claude is awesome"


class TestIsSilenced:
    """Test alert silence checking functionality."""

    @pytest.mark.asyncio
    async def test_is_silenced_no_silence_records(
        self, db_session: AsyncSession
    ) -> None:
        """is_silenced should return False when no silence records exist."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        result = await AlertService.is_silenced(db_session, project.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_silenced_active_global_silence(
        self, db_session: AsyncSession
    ) -> None:
        """is_silenced should return True when global silence is active."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=None,
            silenced_until=datetime.now(timezone.utc) + timedelta(hours=1),
            reason="Maintenance window",
        )
        db_session.add(silence)
        await db_session.commit()

        result = await AlertService.is_silenced(db_session, project.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_silenced_expired_silence(self, db_session: AsyncSession) -> None:
        """is_silenced should return False when silence has expired."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=None,
            silenced_until=datetime.now(timezone.utc) - timedelta(hours=1),
            reason="Past maintenance",
        )
        db_session.add(silence)
        await db_session.commit()

        result = await AlertService.is_silenced(db_session, project.id)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_silenced_indefinite_silence(
        self, db_session: AsyncSession
    ) -> None:
        """is_silenced should return True for indefinite silence (null until)."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=None,
            silenced_until=None,
            reason="Indefinite silence",
        )
        db_session.add(silence)
        await db_session.commit()

        result = await AlertService.is_silenced(db_session, project.id)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_silenced_specific_alert_silenced(
        self, db_session: AsyncSession
    ) -> None:
        """is_silenced should return True when specific alert is silenced."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=alert_def.id,
            silenced_until=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(silence)
        await db_session.commit()

        result = await AlertService.is_silenced(
            db_session, project.id, alert_definition_id=alert_def.id
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_is_silenced_different_alert_not_silenced(
        self, db_session: AsyncSession
    ) -> None:
        """is_silenced should return False when different alert is silenced."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def_1 = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        alert_def_2 = AlertDefinitionDB(
            name="quality_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add_all([alert_def_1, alert_def_2])
        await db_session.commit()
        await db_session.refresh(alert_def_1)
        await db_session.refresh(alert_def_2)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=alert_def_1.id,
            silenced_until=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(silence)
        await db_session.commit()

        result = await AlertService.is_silenced(
            db_session, project.id, alert_definition_id=alert_def_2.id
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_is_silenced_global_silence_affects_specific_alert(
        self, db_session: AsyncSession
    ) -> None:
        """is_silenced should return True when global silence affects specific alert check."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        silence = AlertSilenceDB(
            project_id=project.id,
            alert_definition_id=None,
            silenced_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db_session.add(silence)
        await db_session.commit()

        result = await AlertService.is_silenced(
            db_session, project.id, alert_definition_id=alert_def.id
        )

        assert result is True


class TestWasNotifiedThisMonth:
    """Test monthly notification throttling functionality."""

    @pytest.mark.asyncio
    async def test_was_notified_no_notifications(
        self, db_session: AsyncSession
    ) -> None:
        """was_notified_this_month should return False when no notifications exist."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        result = await AlertService.was_notified_this_month(
            db_session, project.id, alert_def.id
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_was_notified_this_month_true(self, db_session: AsyncSession) -> None:
        """was_notified_this_month should return True when notified this month."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert_def.id,
            channel_id="C123ABC",
            message="Budget alert triggered",
            status="sent",
        )
        db_session.add(notification)
        await db_session.commit()

        result = await AlertService.was_notified_this_month(
            db_session, project.id, alert_def.id
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_was_notified_failed_notification_not_counted(
        self, db_session: AsyncSession
    ) -> None:
        """was_notified_this_month should not count failed notifications."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert_def.id,
            channel_id="C123ABC",
            message="Budget alert triggered",
            status="failed",
            error_message="Channel not found",
        )
        db_session.add(notification)
        await db_session.commit()

        result = await AlertService.was_notified_this_month(
            db_session, project.id, alert_def.id
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_was_notified_different_alert_not_counted(
        self, db_session: AsyncSession
    ) -> None:
        """was_notified_this_month should not count notifications for different alerts."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def_1 = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        alert_def_2 = AlertDefinitionDB(
            name="quality_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add_all([alert_def_1, alert_def_2])
        await db_session.commit()
        await db_session.refresh(alert_def_1)
        await db_session.refresh(alert_def_2)

        notification = AlertNotificationDB(
            project_id=project.id,
            alert_definition_id=alert_def_1.id,
            channel_id="C123ABC",
            message="Budget alert",
            status="sent",
        )
        db_session.add(notification)
        await db_session.commit()

        result = await AlertService.was_notified_this_month(
            db_session, project.id, alert_def_2.id
        )

        assert result is False


class TestGetTemplate:
    """Test message template retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_template_returns_template(
        self, db_session: AsyncSession
    ) -> None:
        """get_template should return the message template text."""
        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        template = MessageTemplateDB(
            alert_definition_id=alert_def.id,
            template_type="initial",
            message_template=":warning: Project {project_name} budget exceeded!",
            is_active=True,
        )
        db_session.add(template)
        await db_session.commit()

        result = await AlertService.get_template(db_session, alert_def.id)

        assert result == ":warning: Project {project_name} budget exceeded!"

    @pytest.mark.asyncio
    async def test_get_template_returns_none_when_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """get_template should return None when no template exists."""
        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        result = await AlertService.get_template(db_session, alert_def.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_template_ignores_inactive(
        self, db_session: AsyncSession
    ) -> None:
        """get_template should ignore inactive templates."""
        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        template = MessageTemplateDB(
            alert_definition_id=alert_def.id,
            template_type="initial",
            message_template="Inactive template",
            is_active=False,
        )
        db_session.add(template)
        await db_session.commit()

        result = await AlertService.get_template(db_session, alert_def.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_template_by_type(self, db_session: AsyncSession) -> None:
        """get_template should return template matching specified type."""
        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        initial_template = MessageTemplateDB(
            alert_definition_id=alert_def.id,
            template_type="initial",
            message_template="Initial message",
            is_active=True,
        )
        reminder_template = MessageTemplateDB(
            alert_definition_id=alert_def.id,
            template_type="reminder",
            message_template="Reminder message",
            is_active=True,
        )
        db_session.add_all([initial_template, reminder_template])
        await db_session.commit()

        result = await AlertService.get_template(
            db_session, alert_def.id, template_type="reminder"
        )

        assert result == "Reminder message"


class TestLogNotification:
    """Test notification logging functionality."""

    @pytest.mark.asyncio
    async def test_log_notification_creates_record(
        self, db_session: AsyncSession
    ) -> None:
        """log_notification should create a notification record."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        notification = await AlertService.log_notification(
            db=db_session,
            project_id=project.id,
            alert_definition_id=alert_def.id,
            channel_id="C123ABC456",
            message="Budget exceeded for Test Project",
            status="sent",
        )

        assert notification.id is not None
        assert notification.project_id == project.id
        assert notification.alert_definition_id == alert_def.id
        assert notification.channel_id == "C123ABC456"
        assert notification.message == "Budget exceeded for Test Project"
        assert notification.status == "sent"
        assert notification.error_message is None

    @pytest.mark.asyncio
    async def test_log_notification_with_error(self, db_session: AsyncSession) -> None:
        """log_notification should store error message for failed notifications."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        notification = await AlertService.log_notification(
            db=db_session,
            project_id=project.id,
            alert_definition_id=alert_def.id,
            channel_id="CINVALID",
            message="Budget exceeded",
            status="failed",
            error_message="channel_not_found",
        )

        assert notification.status == "failed"
        assert notification.error_message == "channel_not_found"

    @pytest.mark.asyncio
    async def test_log_notification_with_metadata(
        self, db_session: AsyncSession
    ) -> None:
        """log_notification should store metadata JSON."""
        project = ProjectDB(name="Test Project")
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        alert_def = AlertDefinitionDB(
            name="budget_alert",
            category="project",
            channel_type="project",
            schedule="daily",
        )
        db_session.add(alert_def)
        await db_session.commit()
        await db_session.refresh(alert_def)

        metadata = {
            "budget_percent": 105.3,
            "threshold": 100,
            "triggered_by": "daily_check",
        }

        notification = await AlertService.log_notification(
            db=db_session,
            project_id=project.id,
            alert_definition_id=alert_def.id,
            channel_id="C123ABC456",
            message="Budget exceeded",
            status="sent",
            metadata=metadata,
        )

        assert notification.metadata_json == metadata
        assert notification.metadata_json["budget_percent"] == pytest.approx(105.3)
