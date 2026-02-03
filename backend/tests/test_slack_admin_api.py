"""Tests for Slack Admin API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.slack import AlertDefinitionDB, MessageTemplateDB, SlackConfigDB


class TestSlackConfigAPI:
    """Tests for Slack config endpoints."""

    @pytest.mark.asyncio
    async def test_get_slack_config_creates_if_not_exists(
        self, client: AsyncClient
    ) -> None:
        """Get slack config creates config if it doesn't exist."""
        response = await client.get("/api/admin/slack/config")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["bot_token_configured"] is False
        assert data["leadership_channel_id"] is None
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_get_slack_config_returns_existing(
        self, client: AsyncClient, db_session
    ) -> None:
        """Get slack config returns existing config."""
        config = SlackConfigDB(
            bot_token_encrypted="xoxb-test-token",
            leadership_channel_id="C12345678",
        )
        db_session.add(config)
        await db_session.commit()

        response = await client.get("/api/admin/slack/config")
        assert response.status_code == 200
        data = response.json()
        assert data["bot_token_configured"] is True
        assert data["leadership_channel_id"] == "C12345678"

    @pytest.mark.asyncio
    async def test_update_slack_config(self, client: AsyncClient) -> None:
        """Update slack config successfully."""
        response = await client.put(
            "/api/admin/slack/config",
            json={
                "bot_token": "xoxb-new-token",
                "leadership_channel_id": "C98765432",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bot_token_configured"] is True
        assert data["leadership_channel_id"] == "C98765432"

    @pytest.mark.asyncio
    async def test_update_slack_config_partial(self, client: AsyncClient) -> None:
        """Update slack config with partial data."""
        await client.put(
            "/api/admin/slack/config",
            json={"bot_token": "xoxb-token"},
        )

        response = await client.put(
            "/api/admin/slack/config",
            json={"leadership_channel_id": "C11111111"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bot_token_configured"] is True
        assert data["leadership_channel_id"] == "C11111111"


class TestSlackConnectionTestAPI:
    """Tests for Slack connection test endpoint."""

    @pytest.mark.asyncio
    async def test_test_connection_no_token(self, client: AsyncClient) -> None:
        """Test connection returns error when no token configured."""
        response = await client.post("/api/admin/slack/test")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "No bot token configured"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, client: AsyncClient) -> None:
        """Test connection returns success with valid token."""
        await client.put(
            "/api/admin/slack/config",
            json={"bot_token": "xoxb-valid-token"},
        )

        mock_response = {"ok": True, "team": "Test Team", "bot_id": "B12345"}
        with patch(
            "app.api.slack_admin.SlackService.test_connection",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await client.post("/api/admin/slack/test")

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["team"] == "Test Team"
        assert data["bot_id"] == "B12345"

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, client: AsyncClient) -> None:
        """Test connection returns error on Slack API failure."""
        await client.put(
            "/api/admin/slack/config",
            json={"bot_token": "xoxb-invalid-token"},
        )

        mock_response = {"ok": False, "error": "invalid_auth"}
        with patch(
            "app.api.slack_admin.SlackService.test_connection",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await client.post("/api/admin/slack/test")

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is False
        assert data["error"] == "invalid_auth"


class TestSlackChannelsAPI:
    """Tests for Slack channels endpoint."""

    @pytest.mark.asyncio
    async def test_list_channels_no_token(self, client: AsyncClient) -> None:
        """List channels returns error when no token configured."""
        response = await client.get("/api/admin/slack/channels")
        assert response.status_code == 400
        assert "No bot token configured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_channels_success(self, client: AsyncClient) -> None:
        """List channels returns channel list."""
        await client.put(
            "/api/admin/slack/config",
            json={"bot_token": "xoxb-valid-token"},
        )

        mock_channels = [
            {"id": "C001", "name": "general", "is_private": False},
            {"id": "C002", "name": "private-channel", "is_private": True},
        ]
        with patch(
            "app.api.slack_admin.SlackService.list_channels",
            new_callable=AsyncMock,
            return_value=mock_channels,
        ):
            response = await client.get("/api/admin/slack/channels")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "C001"
        assert data[0]["name"] == "general"
        assert data[0]["is_private"] is False
        assert data[1]["is_private"] is True


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
    async def test_update_alert_definition_not_found(
        self, client: AsyncClient
    ) -> None:
        """Update alert definition returns 404 for non-existent alert."""
        response = await client.put(
            "/api/admin/alerts/99999",
            json={"is_enabled": False},
        )
        assert response.status_code == 404
        assert "Alert definition not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_alert_templates(
        self, client: AsyncClient, db_session
    ) -> None:
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
    async def test_update_message_template_not_found(
        self, client: AsyncClient
    ) -> None:
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
