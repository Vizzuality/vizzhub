"""Shared Slack utility functions for worker modules."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.slack import SlackConfigDB


async def get_slack_config(db: AsyncSession) -> SlackConfigDB | None:
    """Get the global Slack configuration."""
    result = await db.execute(select(SlackConfigDB).limit(1))
    return result.scalar_one_or_none()
