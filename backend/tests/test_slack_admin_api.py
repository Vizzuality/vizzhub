"""Tests for Slack Alert and Template Admin API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.token_encryption import encrypt_token
from app.core.models.integration_setting import IntegrationSettingDB
from app.core.models.oauth import OAuthTokenDB
from app.models.slack import AlertDefinitionDB, MessageTemplateDB


class TestAlertDefinitionsAPI:
    """Tests for alert definitions endpoints."""

    @pytest.mark.asyncio
    async def test_list_alert_definitions_empty(self, client: AsyncClient) -> None:
        """List alert definitions returns empty list when none exist."""
        response = await client.get("/api/admin/alerts/")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_alert_definitions(
        self, client: AsyncClient, db_session
    ) -> None:
        """List alert definitions returns all definitions."""
        alert1 = AlertDefinitionDB(
            name="test_alert_1",
            description="Test alert 1",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={"threshold": 70},
        )
        alert2 = AlertDefinitionDB(
            name="test_alert_2",
            category="project",
            channel_type="project",
            schedule="daily",
            is_enabled=False,
            config_json={},
        )
        db_session.add_all([alert1, alert2])
        await db_session.commit()

        response = await client.get("/api/admin/alerts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "test_alert_1"
        assert data[0]["is_enabled"] is True
        assert data[1]["name"] == "test_alert_2"
        assert data[1]["is_enabled"] is False

    @pytest.mark.asyncio
    async def test_update_alert_definition(
        self, client: AsyncClient, db_session
    ) -> None:
        """Update alert definition successfully."""
        alert = AlertDefinitionDB(
            name="test_alert",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={"threshold": 70},
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        response = await client.put(
            f"/api/admin/alerts/{alert.id}",
            json={"is_enabled": False, "config_json": {"threshold": 80}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_enabled"] is False
        assert data["config_json"]["threshold"] == 80

    @pytest.mark.asyncio
    async def test_update_alert_definition_not_found(self, client: AsyncClient) -> None:
        """Update alert definition returns 404 for non-existent alert."""
        response = await client.put(
            "/api/admin/alerts/99999",
            json={"is_enabled": False},
        )
        assert response.status_code == 404
        assert "Alert definition not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_alert_templates(self, client: AsyncClient, db_session) -> None:
        """Get alert templates returns templates for alert."""
        alert = AlertDefinitionDB(
            name="test_alert",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        template1 = MessageTemplateDB(
            alert_definition_id=alert.id,
            template_type="initial",
            message_template="Initial message: {project_name}",
            is_active=True,
        )
        template2 = MessageTemplateDB(
            alert_definition_id=alert.id,
            template_type="reminder",
            message_template="Reminder: {project_name}",
            is_active=True,
        )
        db_session.add_all([template1, template2])
        await db_session.commit()

        response = await client.get(f"/api/admin/alerts/{alert.id}/templates")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_alert_templates_not_found(self, client: AsyncClient) -> None:
        """Get alert templates returns 404 for non-existent alert."""
        response = await client.get("/api/admin/alerts/99999/templates")
        assert response.status_code == 404
        assert "Alert definition not found" in response.json()["detail"]


class TestAlertTestEndpoint:
    """Tests for the alert test endpoint using new integration tables."""

    @pytest.mark.asyncio
    async def test_test_alert_no_token(self, client: AsyncClient, db_session) -> None:
        """Test alert returns error when no Slack token configured."""
        alert = AlertDefinitionDB(
            name="test_alert",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        response = await client.post(f"/api/admin/alerts/{alert.id}/test")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "No Slack bot token configured" in data["error"]

    @pytest.mark.asyncio
    async def test_test_alert_no_channel(self, client: AsyncClient, db_session) -> None:
        """Test alert returns error when no leadership channel configured."""
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
        db_session.add(token)

        alert = AlertDefinitionDB(
            name="test_alert",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        response = await client.post(f"/api/admin/alerts/{alert.id}/test")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert "No leadership channel configured" in data["error"]

    @pytest.mark.asyncio
    async def test_test_alert_success(self, client: AsyncClient, db_session) -> None:
        """Test alert sends message successfully."""
        token = OAuthTokenDB(
            provider="slack",
            access_token=encrypt_token("xoxb-test-token"),
            token_type="bot",
        )
        db_session.add(token)

        setting = IntegrationSettingDB(
            provider="slack",
            key="leadership_channel_id",
            value="C_LEADERSHIP",
        )
        db_session.add(setting)

        alert = AlertDefinitionDB(
            name="test_alert",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        with patch(
            "app.api.slack_admin.SlackService.send_message",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ):
            response = await client.post(f"/api/admin/alerts/{alert.id}/test")

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["channel_id"] == "C_LEADERSHIP"

    @pytest.mark.asyncio
    async def test_test_alert_not_found(self, client: AsyncClient) -> None:
        """Test alert returns 404 for non-existent alert."""
        response = await client.post("/api/admin/alerts/99999/test")
        assert response.status_code == 404


class TestMessageTemplatesAPI:
    """Tests for message templates endpoints."""

    @pytest.mark.asyncio
    async def test_update_message_template(
        self, client: AsyncClient, db_session
    ) -> None:
        """Update message template successfully."""
        alert = AlertDefinitionDB(
            name="test_alert",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        template = MessageTemplateDB(
            alert_definition_id=alert.id,
            template_type="initial",
            message_template="Old message",
            is_active=True,
        )
        db_session.add(template)
        await db_session.commit()
        await db_session.refresh(template)

        response = await client.put(
            f"/api/admin/templates/{template.id}",
            json={
                "message_template": "New message: {project_name}",
                "is_active": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message_template"] == "New message: {project_name}"
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_update_message_template_not_found(self, client: AsyncClient) -> None:
        """Update message template returns 404 for non-existent template."""
        response = await client.put(
            "/api/admin/templates/99999",
            json={"message_template": "New message"},
        )
        assert response.status_code == 404
        assert "Message template not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_message_template_partial(
        self, client: AsyncClient, db_session
    ) -> None:
        """Update message template with partial data."""
        alert = AlertDefinitionDB(
            name="test_alert",
            category="business",
            channel_type="leadership",
            schedule="daily",
            is_enabled=True,
            config_json={},
        )
        db_session.add(alert)
        await db_session.commit()
        await db_session.refresh(alert)

        template = MessageTemplateDB(
            alert_definition_id=alert.id,
            template_type="initial",
            message_template="Original message",
            is_active=True,
        )
        db_session.add(template)
        await db_session.commit()
        await db_session.refresh(template)

        response = await client.put(
            f"/api/admin/templates/{template.id}",
            json={"is_active": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message_template"] == "Original message"
        assert data["is_active"] is False
