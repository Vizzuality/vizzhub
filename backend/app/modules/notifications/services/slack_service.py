"""Slack API service."""

import asyncio
import random
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_SLACK_RATE_LIMIT_MAX_RETRIES = 2
_SLACK_RATE_LIMIT_MAX_WAIT = 30


class SlackAPIError(RuntimeError):
    """Raised when Slack returns ``ok=false`` or an HTTP failure."""

    def __init__(self, slack_error: str, status_code: int | None = None):
        super().__init__(f"Slack API error: {slack_error}")
        self.slack_error = slack_error
        self.status_code = status_code


async def _post_with_rate_limit_retry(
    client: httpx.AsyncClient, url: str, **kwargs
) -> httpx.Response:
    """POST to Slack, sleeping per `retry-after` on 429 (max 2 retries)."""
    for attempt in range(_SLACK_RATE_LIMIT_MAX_RETRIES + 1):
        response = await client.post(url, **kwargs)
        if response.status_code != 429:
            return response
        retry_after = int(response.headers.get("retry-after", "1"))
        wait = min(retry_after, _SLACK_RATE_LIMIT_MAX_WAIT) + random.uniform(0, 0.5)
        logger.warning(
            "slack_rate_limited",
            url=url,
            retry_after=retry_after,
            attempt=attempt + 1,
        )
        await asyncio.sleep(wait)
    return response  # last response (still 429)


class SlackService:
    """Service for interacting with Slack API."""

    BASE_URL = "https://slack.com/api"

    @staticmethod
    async def send_message(
        bot_token: str,
        channel_id: str,
        message: str,
        *,
        unfurl_links: bool = True,
        unfurl_media: bool = True,
    ) -> dict[str, Any]:
        """Send a message to a Slack channel.

        Args:
            bot_token: Slack bot OAuth token (xoxb-...).
            channel_id: Slack channel ID to send message to.
            message: Message text (supports Slack markdown).
            unfurl_links: Enable link previews.
            unfurl_media: Enable media previews.

        Returns:
            Slack API response containing ok status and message timestamp.

        Raises:
            SlackAPIError: when Slack returns ``ok=false`` or a non-2xx HTTP.
            httpx.HTTPError: transport failure.
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await _post_with_rate_limit_retry(
                    client,
                    f"{SlackService.BASE_URL}/chat.postMessage",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    json={
                        "channel": channel_id,
                        "text": message,
                        "mrkdwn": True,
                        "unfurl_links": unfurl_links,
                        "unfurl_media": unfurl_media,
                    },
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "slack_send_failed",
                    channel_id=channel_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                return {"ok": False, "error": f"transport_error: {type(exc).__name__}"}

            if response.status_code >= 400:
                logger.warning(
                    "slack_send_failed",
                    channel_id=channel_id,
                    status_code=response.status_code,
                )
                return {
                    "ok": False,
                    "error": f"http_{response.status_code}",
                }
            try:
                data = response.json()
            except ValueError:
                logger.warning(
                    "slack_send_failed",
                    channel_id=channel_id,
                    error="non_json_response",
                )
                return {"ok": False, "error": "non_json_response"}

            if not data.get("ok"):
                logger.warning(
                    "slack_send_failed",
                    channel_id=channel_id,
                    slack_error=data.get("error", "unknown"),
                )
            else:
                logger.info(
                    "slack_send_succeeded",
                    channel_id=channel_id,
                    ts=data.get("ts"),
                )
            return data

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
                    "exclude_archived": True,
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

        # Sort channels alphabetically by name
        channels.sort(key=lambda c: c.get("name", "").lower())
        return channels

    @staticmethod
    def extract_display_name(slack_user: dict[str, Any]) -> str | None:
        """Extract the best display name from a Slack user object."""
        profile = slack_user.get("profile", {})
        return profile.get("display_name") or profile.get("real_name") or slack_user.get("name")

    @staticmethod
    async def lookup_user_by_email(
        bot_token: str,
        email: str,
    ) -> dict[str, Any] | None:
        """Look up a Slack user by email address.

        Requires the `users:read.email` scope on the bot token.

        Returns:
            Slack user object if found, None otherwise.
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SlackService.BASE_URL}/users.lookupByEmail",
                headers={"Authorization": f"Bearer {bot_token}"},
                params={"email": email},
            )
            data = response.json()
            if data.get("ok"):
                return data["user"]
            return None

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
