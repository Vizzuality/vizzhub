"""Daily devstack SHA refresh — cron task."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.services.sha_refresh import refresh_all_shas


async def refresh_devstack_shas(ctx: dict) -> dict:
    """Refresh GitHub SHAs for all active devstack entries. Daily at 6 AM UTC."""
    db: AsyncSession = ctx["db"]
    return await refresh_all_shas(db)
