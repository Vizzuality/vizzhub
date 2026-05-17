"""Worker heartbeat for health checks."""

from datetime import UTC, datetime

import structlog

logger = structlog.get_logger()

HEARTBEAT_KEY = "vizzhub:worker:heartbeat"
HEARTBEAT_TTL_S = 120


async def write_heartbeat(ctx: dict) -> None:
    """Write heartbeat timestamp to Redis with TTL."""
    redis_client = ctx.get("redis_client")
    if redis_client is None:
        return

    try:
        now = datetime.now(UTC).isoformat()
        await redis_client.set(HEARTBEAT_KEY, now, ex=HEARTBEAT_TTL_S)
    except Exception:
        logger.warning("heartbeat_write_failed", exc_info=True)
