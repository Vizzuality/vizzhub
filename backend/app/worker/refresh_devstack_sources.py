"""Daily devstack source refresh — cron task. Refreshes GitHub SHAs + npm versions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.services.sha_refresh import refresh_all_sources_tracked


async def refresh_devstack_sources(ctx: dict) -> dict:
    """Refresh GitHub SHAs and npm latest versions. Daily at 6 AM UTC."""
    db: AsyncSession = ctx["db"]
    return await refresh_all_sources_tracked(db)
