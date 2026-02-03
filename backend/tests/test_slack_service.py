"""Tests for Slack API service.

This module tests the SlackService which handles Slack API interactions
including sending messages, listing channels, and testing bot connections.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.slack_service import SlackService


class TestSendMessage:
    """Test Slack message sending functionality."""

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """send_message should return success response from Slack API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "ts": "1234567890.123456"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await SlackService.send_message(
                bot_token="xoxb-test-token",
                channel_id="C123ABC456",
                message="Test message",
            )

            assert result["ok"] is True
            assert result["ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_send_message_calls_correct_endpoint(self) -> None:
        """send_message should POST to chat.postMessage endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            await SlackService.send_message(
                bot_token="xoxb-test-token",
                channel_id="C123ABC456",
                message="Test message",
            )

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://slack.com/api/chat.postMessage"

    @pytest.mark.asyncio
    async def test_send_message_includes_authorization_header(self) -> None:
        """send_message should include Bearer token in Authorization header."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            await SlackService.send_message(
                bot_token="xoxb-my-bot-token",
                channel_id="C123",
                message="Hello",
            )

            call_args = mock_client.post.call_args
            assert (
                call_args[1]["headers"]["Authorization"] == "Bearer xoxb-my-bot-token"
            )

    @pytest.mark.asyncio
    async def test_send_message_includes_correct_payload(self) -> None:
        """send_message should include channel, text, and mrkdwn in payload."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            await SlackService.send_message(
                bot_token="xoxb-token",
                channel_id="C456DEF789",
                message="Hello *world*!",
            )

            call_args = mock_client.post.call_args
            json_payload = call_args[1]["json"]
            assert json_payload["channel"] == "C456DEF789"
            assert json_payload["text"] == "Hello *world*!"
            assert json_payload["mrkdwn"] is True

    @pytest.mark.asyncio
    async def test_send_message_returns_error_response(self) -> None:
        """send_message should return error response when API fails."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "channel_not_found",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await SlackService.send_message(
                bot_token="xoxb-token",
                channel_id="CINVALID",
                message="Test",
            )

            assert result["ok"] is False
            assert result["error"] == "channel_not_found"


class TestListChannels:
    """Test Slack channel listing functionality."""

    @pytest.mark.asyncio
    async def test_list_channels_returns_channels(self) -> None:
        """list_channels should return list of channel objects."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channels": [
                {"id": "C123", "name": "general"},
                {"id": "C456", "name": "random"},
            ],
            "response_metadata": {"next_cursor": ""},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            channels = await SlackService.list_channels("xoxb-test")

            assert len(channels) == 2
            assert channels[0]["name"] == "general"
            assert channels[1]["name"] == "random"

    @pytest.mark.asyncio
    async def test_list_channels_calls_correct_endpoint(self) -> None:
        """list_channels should GET from conversations.list endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channels": [],
            "response_metadata": {"next_cursor": ""},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            await SlackService.list_channels("xoxb-test")

            mock_client.get.assert_called_once()
            call_args = mock_client.get.call_args
            assert call_args[0][0] == "https://slack.com/api/conversations.list"

    @pytest.mark.asyncio
    async def test_list_channels_includes_channel_types(self) -> None:
        """list_channels should request both public and private channels."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "channels": [],
            "response_metadata": {"next_cursor": ""},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            await SlackService.list_channels("xoxb-test")

            call_args = mock_client.get.call_args
            params = call_args[1]["params"]
            assert params["types"] == "public_channel,private_channel"
            assert params["limit"] == 200

    @pytest.mark.asyncio
    async def test_list_channels_handles_pagination(self) -> None:
        """list_channels should fetch all pages when cursor is present."""
        first_response = MagicMock()
        first_response.json.return_value = {
            "ok": True,
            "channels": [{"id": "C1", "name": "page1"}],
            "response_metadata": {"next_cursor": "cursor123"},
        }

        second_response = MagicMock()
        second_response.json.return_value = {
            "ok": True,
            "channels": [{"id": "C2", "name": "page2"}],
            "response_metadata": {"next_cursor": ""},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [first_response, second_response]

            channels = await SlackService.list_channels("xoxb-test")

            assert len(channels) == 2
            assert channels[0]["name"] == "page1"
            assert channels[1]["name"] == "page2"
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_list_channels_passes_cursor_in_params(self) -> None:
        """list_channels should include cursor in subsequent requests."""
        first_response = MagicMock()
        first_response.json.return_value = {
            "ok": True,
            "channels": [{"id": "C1", "name": "first"}],
            "response_metadata": {"next_cursor": "next_page_cursor"},
        }

        second_response = MagicMock()
        second_response.json.return_value = {
            "ok": True,
            "channels": [],
            "response_metadata": {"next_cursor": ""},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.side_effect = [first_response, second_response]

            await SlackService.list_channels("xoxb-test")

            second_call_args = mock_client.get.call_args_list[1]
            assert second_call_args[1]["params"]["cursor"] == "next_page_cursor"

    @pytest.mark.asyncio
    async def test_list_channels_returns_empty_on_error(self) -> None:
        """list_channels should return empty list when API returns error."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "invalid_auth",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response

            channels = await SlackService.list_channels("xoxb-invalid")

            assert channels == []


class TestTestConnection:
    """Test Slack bot connection testing functionality."""

    @pytest.mark.asyncio
    async def test_test_connection_returns_success(self) -> None:
        """test_connection should return success response with team info."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "team": "TestTeam",
            "bot_id": "B123ABC",
            "user_id": "U456DEF",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await SlackService.test_connection("xoxb-valid-token")

            assert result["ok"] is True
            assert result["team"] == "TestTeam"
            assert result["bot_id"] == "B123ABC"

    @pytest.mark.asyncio
    async def test_test_connection_calls_correct_endpoint(self) -> None:
        """test_connection should POST to auth.test endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            await SlackService.test_connection("xoxb-test")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://slack.com/api/auth.test"

    @pytest.mark.asyncio
    async def test_test_connection_includes_authorization(self) -> None:
        """test_connection should include Bearer token in headers."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            await SlackService.test_connection("xoxb-my-secret-token")

            call_args = mock_client.post.call_args
            assert (
                call_args[1]["headers"]["Authorization"]
                == "Bearer xoxb-my-secret-token"
            )

    @pytest.mark.asyncio
    async def test_test_connection_returns_error_for_invalid_token(self) -> None:
        """test_connection should return error response for invalid token."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": False,
            "error": "invalid_auth",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response

            result = await SlackService.test_connection("xoxb-invalid")

            assert result["ok"] is False
            assert result["error"] == "invalid_auth"
