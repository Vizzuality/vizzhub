"""Redis-backed score cache with graceful degradation."""

import json
import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

CACHE_PREFIX = "scores:latest"
CACHE_TTL = 3600  # 1 hour safety net


async def create_score_cache(
    host: str, port: int, password: str = "",
) -> tuple[Redis | None, "ScoreCacheService | None"]:
    """Create a Redis client and ScoreCacheService, or (None, None) on failure."""
    redis_client = None
    try:
        redis_client = Redis(
            host=host,
            port=port,
            password=password or None,
            decode_responses=True,
        )
        await redis_client.ping()
        return redis_client, ScoreCacheService(redis_client)
    except Exception:
        logger.warning("Redis unavailable — score cache disabled", exc_info=True)
        if redis_client:
            await redis_client.aclose()
        return None, None


class ScoreCacheService:
    """Cache for computed score responses.

    All methods silently degrade on Redis errors — callers never see exceptions.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _key(self, project_id: str, snapshot_type: str) -> str:
        return f"{CACHE_PREFIX}:{project_id}:{snapshot_type}"

    async def get(self, project_id: str, snapshot_type: str = "cumulative") -> dict | None:
        try:
            raw = await self._redis.get(self._key(project_id, snapshot_type))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.warning("score_cache.get failed for %s", project_id, exc_info=True)
            return None

    async def mget(
        self, project_ids: list[str], snapshot_type: str = "cumulative"
    ) -> dict[str, dict | None]:
        if not project_ids:
            return {}
        try:
            keys = [self._key(pid, snapshot_type) for pid in project_ids]
            values = await self._redis.mget(keys)
            result: dict[str, dict | None] = {}
            for pid, raw in zip(project_ids, values):
                result[pid] = json.loads(raw) if raw else None
            return result
        except Exception:
            logger.warning("score_cache.mget failed", exc_info=True)
            return dict.fromkeys(project_ids)

    async def set(
        self, project_id: str, data: dict, snapshot_type: str = "cumulative"
    ) -> None:
        try:
            await self._redis.set(
                self._key(project_id, snapshot_type),
                json.dumps(data),
                ex=CACHE_TTL,
            )
        except Exception:
            logger.warning("score_cache.set failed for %s", project_id, exc_info=True)

    async def invalidate(self, project_id: str) -> None:
        try:
            keys = [
                self._key(project_id, "cumulative"),
                self._key(project_id, "punctual"),
            ]
            await self._redis.delete(*keys)
        except Exception:
            logger.warning(
                "score_cache.invalidate failed for %s", project_id, exc_info=True
            )

    async def invalidate_all(self) -> None:
        try:
            cursor = 0
            while True:
                cursor, keys = await self._redis.scan(
                    cursor, match=f"{CACHE_PREFIX}:*", count=100
                )
                if keys:
                    await self._redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            logger.warning("score_cache.invalidate_all failed", exc_info=True)
