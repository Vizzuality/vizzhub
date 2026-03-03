"""Shared Slack utility functions for worker modules."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.integration_token_service import IntegrationTokenService


async def get_slack_bot_token(db: AsyncSession) -> str | None:
    """Get the decrypted Slack bot token."""
    return await IntegrationTokenService.get_token(db, "slack")


async def get_slack_leadership_channel(db: AsyncSession) -> str | None:
    """Get the leadership channel ID."""
    return await IntegrationTokenService.get_setting(
        db, "slack", "leadership_channel_id"
    )
