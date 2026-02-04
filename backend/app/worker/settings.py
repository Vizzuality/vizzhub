"""ARQ worker configuration."""

from arq.connections import RedisSettings
from arq.cron import cron

from app.config import get_settings
from app.database import async_session_maker

settings = get_settings()


async def startup(ctx: dict) -> None:
    """Initialize worker context on startup."""
    ctx["db_session_maker"] = async_session_maker


async def shutdown(ctx: dict) -> None:
    """Cleanup on worker shutdown."""
    pass


async def on_job_start(ctx: dict) -> None:
    """Create DB session before each job."""
    ctx["db"] = ctx["db_session_maker"]()


async def on_job_end(ctx: dict) -> None:
    """Close DB session after each job."""
    if "db" in ctx:
        await ctx["db"].close()


class WorkerSettings:
    """ARQ worker settings."""

    redis_settings = RedisSettings(
        host=settings.redis_host or "localhost",
        port=settings.redis_port,
        password=settings.redis_password or None,
    )

    on_startup = startup
    on_shutdown = shutdown
    on_job_start = on_job_start
    on_job_end = on_job_end

    max_jobs = 5
    job_timeout = 3600  # 1 hour
    keep_result = 86400  # 24 hours
    retry_jobs = True
    max_tries = 2


# Register tasks at module level for ARQ discovery
from app.worker.tasks import capture_history_task  # noqa: E402
from app.worker.check_dependabot import check_dependabot_alerts  # noqa: E402
from app.worker.check_business_alerts import check_business_alerts  # noqa: E402

WorkerSettings.functions = [
    capture_history_task,
    check_dependabot_alerts,
    check_business_alerts,
]

# Register cron jobs for scheduled execution
WorkerSettings.cron_jobs = [
    cron(check_dependabot_alerts, hour=8, minute=0),
    cron(check_business_alerts, hour=9, minute=0),
]
