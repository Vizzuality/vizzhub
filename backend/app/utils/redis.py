"""Shared Redis connection utilities."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import get_settings


async def get_redis_pool() -> ArqRedis:
    """Get ARQ Redis connection pool."""
    settings = get_settings()
    return await create_pool(
        RedisSettings(
            host=settings.redis_host or "localhost",
            port=settings.redis_port,
            password=settings.redis_password or None,
        )
    )
