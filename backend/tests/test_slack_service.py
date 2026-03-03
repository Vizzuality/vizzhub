"""Tests for Slack API service.

This module tests the SlackService which handles Slack API interactions
including sending messages, listing channels, and testing bot connections.

Uses respx to intercept actual httpx calls at the transport layer,
verifying URLs, headers, and request bodies sent to the Slack API.
"""

import json

import pytest
import respx
from httpx import Response

from app.modules.scorecard.services.slack_service import SlackService

CHAT_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"
CONVERSATIONS_LIST_URL = "https://slack.com/api/conversations.list"
AUTH_TEST_URL = "https://slack.com/api/auth.test"


class TestSendMessage:
    """Test Slack message sending functionality."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_success(self) -> None:
        """send_message should return success response from Slack API."""
        route = respx.post(CHAT_POST_MESSAGE_URL).mock(
            return_value=Response(200, json={"ok": True, "ts": "1234567890.123456"})
        )

        result = await SlackService.send_message(
            bot_token="xoxb-test-token",
            channel_id="C123ABC456",
            message="Test message",
        )

        assert result["ok"] is True
        assert result["ts"] == "1234567890.123456"
        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_calls_correct_endpoint(self) -> None:
        """send_message should POST to chat.postMessage endpoint."""
        route = respx.post(CHAT_POST_MESSAGE_URL).mock(
            return_value=Response(200, json={"ok": True})
        )

        await SlackService.send_message(
            bot_token="xoxb-test-token",
            channel_id="C123ABC456",
            message="Test message",
        )

        assert route.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_includes_authorization_header(self) -> None:
        """send_message should include Bearer token in Authorization header."""
        route = respx.post(CHAT_POST_MESSAGE_URL).mock(
            return_value=Response(200, json={"ok": True})
        )

        await SlackService.send_message(
            bot_token="xoxb-my-bot-token",
            channel_id="C123",
            message="Hello",
        )

        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer xoxb-my-bot-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_includes_correct_payload(self) -> None:
        """send_message should include channel, text, and mrkdwn in payload."""
        route = respx.post(CHAT_POST_MESSAGE_URL).mock(
            return_value=Response(200, json={"ok": True})
        )

        await SlackService.send_message(
            bot_token="xoxb-token",
            channel_id="C456DEF789",
            message="Hello *world*!",
        )

        request = route.calls.last.request
        body = json.loads(request.content)
        assert body["channel"] == "C456DEF789"
        assert body["text"] == "Hello *world*!"
        assert body["mrkdwn"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_message_returns_error_response(self) -> None:
        """send_message should return error response when API fails."""
        route = respx.post(CHAT_POST_MESSAGE_URL).mock(
            return_value=Response(
                200, json={"ok": False, "error": "channel_not_found"}
            )
        )

        result = await SlackService.send_message(
            bot_token="xoxb-token",
            channel_id="CINVALID",
            message="Test",
        )

        assert result["ok"] is False
        assert result["error"] == "channel_not_found"
        assert route.called


class TestListChannels:
    """Test Slack channel listing functionality."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_channels_returns_channels(self) -> None:
        """list_channels should return list of channel objects."""
        route = respx.get(CONVERSATIONS_LIST_URL).mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": [
                        {"id": "C123", "name": "general"},
                        {"id": "C456", "name": "random"},
                    ],
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )

        channels = await SlackService.list_channels("xoxb-test")

        assert len(channels) == 2
        assert channels[0]["name"] == "general"
        assert channels[1]["name"] == "random"
        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_channels_calls_correct_endpoint(self) -> None:
        """list_channels should GET from conversations.list endpoint."""
        route = respx.get(CONVERSATIONS_LIST_URL).mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": [],
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )

        await SlackService.list_channels("xoxb-test")

        assert route.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_channels_includes_channel_types(self) -> None:
        """list_channels should request both public and private channels."""
        route = respx.get(CONVERSATIONS_LIST_URL).mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "channels": [],
                    "response_metadata": {"next_cursor": ""},
                },
            )
        )

        await SlackService.list_channels("xoxb-test")

        request = route.calls.last.request
        assert "types=public_channel%2Cprivate_channel" in str(request.url)
        assert "limit=200" in str(request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_channels_handles_pagination(self) -> None:
        """list_channels should fetch all pages when cursor is present."""
        route = respx.get(CONVERSATIONS_LIST_URL).mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "ok": True,
                        "channels": [{"id": "C1", "name": "page1"}],
                        "response_metadata": {"next_cursor": "cursor123"},
                    },
                ),
                Response(
                    200,
                    json={
                        "ok": True,
                        "channels": [{"id": "C2", "name": "page2"}],
                        "response_metadata": {"next_cursor": ""},
                    },
                ),
            ]
        )

        channels = await SlackService.list_channels("xoxb-test")

        assert len(channels) == 2
        assert channels[0]["name"] == "page1"
        assert channels[1]["name"] == "page2"
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_channels_passes_cursor_in_params(self) -> None:
        """list_channels should include cursor in subsequent requests."""
        route = respx.get(CONVERSATIONS_LIST_URL).mock(
            side_effect=[
                Response(
                    200,
                    json={
                        "ok": True,
                        "channels": [{"id": "C1", "name": "first"}],
                        "response_metadata": {"next_cursor": "next_page_cursor"},
                    },
                ),
                Response(
                    200,
                    json={
                        "ok": True,
                        "channels": [],
                        "response_metadata": {"next_cursor": ""},
                    },
                ),
            ]
        )

        await SlackService.list_channels("xoxb-test")

        second_request = route.calls[1].request
        assert "cursor=next_page_cursor" in str(second_request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_list_channels_returns_empty_on_error(self) -> None:
        """list_channels should return empty list when API returns error."""
        route = respx.get(CONVERSATIONS_LIST_URL).mock(
            return_value=Response(
                200, json={"ok": False, "error": "invalid_auth"}
            )
        )

        channels = await SlackService.list_channels("xoxb-invalid")

        assert channels == []
        assert route.called


class TestTestConnection:
    """Test Slack bot connection testing functionality."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_test_connection_returns_success(self) -> None:
        """test_connection should return success response with team info."""
        route = respx.post(AUTH_TEST_URL).mock(
            return_value=Response(
                200,
                json={
                    "ok": True,
                    "team": "TestTeam",
                    "bot_id": "B123ABC",
                    "user_id": "U456DEF",
                },
            )
        )

        result = await SlackService.test_connection("xoxb-valid-token")

        assert result["ok"] is True
        assert result["team"] == "TestTeam"
        assert result["bot_id"] == "B123ABC"
        assert route.called

    @pytest.mark.asyncio
    @respx.mock
    async def test_test_connection_calls_correct_endpoint(self) -> None:
        """test_connection should POST to auth.test endpoint."""
        route = respx.post(AUTH_TEST_URL).mock(
            return_value=Response(200, json={"ok": True})
        )

        await SlackService.test_connection("xoxb-test")

        assert route.call_count == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_test_connection_includes_authorization(self) -> None:
        """test_connection should include Bearer token in headers."""
        route = respx.post(AUTH_TEST_URL).mock(
            return_value=Response(200, json={"ok": True})
        )

        await SlackService.test_connection("xoxb-my-secret-token")

        request = route.calls.last.request
        assert request.headers["Authorization"] == "Bearer xoxb-my-secret-token"

    @pytest.mark.asyncio
    @respx.mock
    async def test_test_connection_returns_error_for_invalid_token(self) -> None:
        """test_connection should return error response for invalid token."""
        route = respx.post(AUTH_TEST_URL).mock(
            return_value=Response(
                200, json={"ok": False, "error": "invalid_auth"}
            )
        )

        result = await SlackService.test_connection("xoxb-invalid")

        assert result["ok"] is False
        assert result["error"] == "invalid_auth"
        assert route.called
