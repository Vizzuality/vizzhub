"""Slack API service."""

import httpx
from typing import Any


class SlackService:
    """Service for interacting with Slack API."""

    BASE_URL = "https://slack.com/api"

    @staticmethod
    async def send_message(
        bot_token: str,
        channel_id: str,
        message: str,
    ) -> dict[str, Any]:
        """Send a message to a Slack channel.

        Args:
            bot_token: Slack bot OAuth token (xoxb-...).
            channel_id: Slack channel ID to send message to.
            message: Message text (supports Slack markdown).

        Returns:
            Slack API response containing ok status and message timestamp.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SlackService.BASE_URL}/chat.postMessage",
                headers={"Authorization": f"Bearer {bot_token}"},
                json={
                    "channel": channel_id,
                    "text": message,
                    "mrkdwn": True,
                },
            )
            return response.json()

    @staticmethod
    async def list_channels(bot_token: str) -> list[dict[str, Any]]:
        """List available Slack channels.

        Fetches all public and private channels the bot has access to,
        handling pagination automatically.

        Args:
            bot_token: Slack bot OAuth token (xoxb-...).

        Returns:
            List of channel objects with id, name, and other metadata.
        """
        channels: list[dict[str, Any]] = []
        cursor: str | None = None

        async with httpx.AsyncClient() as client:
            while True:
                params: dict[str, Any] = {
                    "types": "public_channel,private_channel",
                    "limit": 200,
                }
                if cursor:
                    params["cursor"] = cursor

                response = await client.get(
                    f"{SlackService.BASE_URL}/conversations.list",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    params=params,
                )
                data = response.json()

                if not data.get("ok"):
                    break

                channels.extend(data.get("channels", []))

                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        return channels

    @staticmethod
    async def test_connection(bot_token: str) -> dict[str, Any]:
        """Test Slack bot token validity.

        Args:
            bot_token: Slack bot OAuth token (xoxb-...).

        Returns:
            Slack API response containing ok status, team name, and bot info.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SlackService.BASE_URL}/auth.test",
                headers={"Authorization": f"Bearer {bot_token}"},
            )
            return response.json()
