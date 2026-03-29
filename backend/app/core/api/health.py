"""Health check endpoints for liveness and readiness probes."""

import asyncio
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import async_session_maker
from app.worker.heartbeat import HEARTBEAT_KEY

logger = structlog.get_logger()

router = APIRouter(prefix="/health", tags=["health"])

DB_TIMEOUT_S = 5
REDIS_TIMEOUT_S = 2


async def _check_database() -> dict[str, Any]:
    """Check database connectivity with SELECT 1."""
    try:
        start = asyncio.get_event_loop().time()
        async with async_session_maker() as session:
            await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=DB_TIMEOUT_S,
            )
        latency_ms = round((asyncio.get_event_loop().time() - start) * 1000)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning("health_check_failed", component="database", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}


def _get_redis_client(request: Request):
    """Extract Redis client from app state, or None if unavailable."""
    score_cache = getattr(request.app.state, "score_cache", None)
    if score_cache is None:
        return None
    return getattr(score_cache, "_redis", None)


async def _check_redis(request: Request) -> dict[str, Any]:
    """Check Redis connectivity with PING."""
    redis_client = _get_redis_client(request)
    if redis_client is None:
        return {"status": "unavailable"}

    try:
        start = asyncio.get_event_loop().time()
        await asyncio.wait_for(redis_client.ping(), timeout=REDIS_TIMEOUT_S)
        latency_ms = round((asyncio.get_event_loop().time() - start) * 1000)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning("health_check_failed", component="redis", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}


async def _check_worker(request: Request) -> dict[str, Any]:
    """Check worker heartbeat key in Redis."""
    redis_client = _get_redis_client(request)
    if redis_client is None:
        return {"status": "unavailable"}

    try:
        heartbeat = await asyncio.wait_for(
            redis_client.get(HEARTBEAT_KEY), timeout=REDIS_TIMEOUT_S,
        )
        if heartbeat is None:
            return {"status": "unhealthy", "error": "no heartbeat"}
        return {
            "status": "healthy",
            "last_heartbeat": heartbeat.decode() if isinstance(heartbeat, bytes) else heartbeat,
        }
    except Exception as exc:
        logger.warning("health_check_failed", component="worker", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Liveness probe — process is running."""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness(request: Request) -> JSONResponse:
    """Readiness probe — all dependencies healthy."""
    db_check, redis_check, worker_check = await asyncio.gather(
        _check_database(),
        _check_redis(request),
        _check_worker(request),
    )

    checks = {
        "database": db_check,
        "redis": redis_check,
        "worker": worker_check,
    }

    all_healthy = all(
        c.get("status") in ("healthy", "unavailable") for c in checks.values()
    )

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
