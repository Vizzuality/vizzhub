"""ARQ worker configuration."""

import os
import uuid

import structlog
from arq.connections import RedisSettings
from arq.cron import cron

from app.config import get_settings
from app.core.logging_config import configure_logging
from app.database import async_session_maker

settings = get_settings()

configure_logging(log_format=settings.log_format, log_level=settings.log_level)
os.environ.setdefault("SERVICE_NAME", "vizzhub-worker")
os.environ.setdefault("APP_ENV", settings.app_env)
if settings.release:
    os.environ.setdefault("RELEASE", settings.release)

logger = structlog.get_logger()


async def startup(ctx: dict) -> None:
    """Initialize worker context on startup."""
    ctx["db_session_maker"] = async_session_maker

    ctx["score_cache"] = None
    ctx["redis_client"] = None
    if settings.redis_host:
        from app.modules.scorecard.services.score_cache import create_score_cache

        redis_client, score_cache = await create_score_cache(
            settings.redis_host,
            settings.redis_port,
            settings.redis_password,
        )
        ctx["redis_client"] = redis_client
        ctx["score_cache"] = score_cache

    from app.worker.heartbeat import write_heartbeat
    await write_heartbeat(ctx)

    logger.info("worker_started")


async def shutdown(ctx: dict) -> None:
    """Cleanup on worker shutdown."""
    redis_client = ctx.get("redis_client")
    if redis_client:
        await redis_client.aclose()
    logger.info("worker_stopped")


async def on_job_start(ctx: dict) -> None:
    """Create DB session and bind job context to structlog."""
    ctx["db"] = ctx["db_session_maker"]()
    job_id = ctx.get("job_id", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(job_id=job_id)


async def on_job_end(ctx: dict) -> None:
    """Close DB session after each job."""
    if "db" in ctx:
        await ctx["db"].close()
    structlog.contextvars.clear_contextvars()


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
from app.worker.collect_iso_snapshot import collect_iso_snapshot  # noqa: E402
from app.worker.monthly_scorecard_capture import monthly_scorecard_capture  # noqa: E402
from app.worker.fetch_exchange_rates import fetch_exchange_rates  # noqa: E402
from app.worker.report_reminder import send_monthly_report_reminder  # noqa: E402
from app.worker.report_confirmation_reminder import send_report_confirmation_reminder  # noqa: E402
from app.worker.rotate_reporting_period import rotate_reporting_period  # noqa: E402
from app.worker.heartbeat import write_heartbeat  # noqa: E402

WorkerSettings.functions = [
    capture_history_task,
    check_dependabot_alerts,
    check_business_alerts,
    collect_iso_snapshot,
    monthly_scorecard_capture,
    fetch_exchange_rates,
    send_monthly_report_reminder,
    send_report_confirmation_reminder,
    rotate_reporting_period,
]

# Register cron jobs for scheduled execution
WorkerSettings.cron_jobs = [
    cron(check_dependabot_alerts, hour=8, minute=0),
    cron(check_business_alerts, hour=9, minute=0),
    cron(collect_iso_snapshot, day=1, hour=6, minute=0),  # Monthly 1st at 6 AM UTC
    cron(monthly_scorecard_capture, day=5, hour=2, minute=0),  # Monthly 5th at 2 AM UTC
    cron(fetch_exchange_rates, hour=14, minute=30),  # Daily — ECB publishes ~14:00 UTC
    cron(send_monthly_report_reminder, hour=10, minute=0),  # Daily — sends only on last business day
    cron(send_report_confirmation_reminder, hour=12, minute=0),  # Daily — sends only on business days 2nd-12th
    cron(rotate_reporting_period, day=15, hour=0, minute=0),  # Monthly 15th at midnight UTC
    cron(write_heartbeat, minute=set(range(60)), run_at_startup=True),
]
