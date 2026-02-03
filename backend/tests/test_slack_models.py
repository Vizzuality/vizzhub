"""Tests for Slack notification models."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slack import (
    AlertCategory,
    AlertDefinitionDB,
    AlertSchedule,
    ChannelType,
    MessageTemplateDB,
    SlackConfigDB,
    TemplateType,
)


class TestSlackConfigModel:
    """Tests for SlackConfigDB model."""

    def test_slack_config_model_exists(self) -> None:
        """Test SlackConfigDB model has correct table name."""
        assert SlackConfigDB.__tablename__ == "slack_config"

    @pytest.mark.asyncio
    async def test_slack_config_creation(self, db_session: AsyncSession) -> None:
        """Test creating a Slack config record."""
        config = SlackConfigDB(
            bot_token_encrypted="encrypted_token_value",
            leadership_channel_id="C123456789",
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)

        assert config.id is not None
        assert config.bot_token_encrypted == "encrypted_token_value"
        assert config.leadership_channel_id == "C123456789"
        assert config.created_at is not None
        assert config.updated_at is not None


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
