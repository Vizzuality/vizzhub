"""Unit tests for ScoreCacheService.

Happy-path tests use fakeredis (in-memory Redis) to verify actual behavior.
Error/resilience tests use AsyncMock to simulate Redis failures.
"""

import json
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from app.modules.scorecard.services.score_cache import CACHE_PREFIX, CACHE_TTL, ScoreCacheService


@pytest.fixture
def redis():
    """In-memory Redis for happy-path tests."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def _make_cache(redis) -> ScoreCacheService:
    return ScoreCacheService(redis)


SAMPLE_SCORES = {
    "indicators": {"p_time": 0.85, "p_cost": 0.9},
    "scores": {"score": 75.0, "dimensions": {}},
}


class TestGet:
    @pytest.mark.asyncio
    async def test_cache_hit(self, redis) -> None:
        key = f"{CACHE_PREFIX}:proj-1:cumulative"
        await redis.set(key, json.dumps(SAMPLE_SCORES))
        cache = _make_cache(redis)

        result = await cache.get("proj-1", "cumulative")

        assert result == SAMPLE_SCORES

    @pytest.mark.asyncio
    async def test_cache_miss(self, redis) -> None:
        cache = _make_cache(redis)

        result = await cache.get("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_redis_error_returns_none(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ConnectionError("Redis down")
        cache = _make_cache(mock_redis)

        result = await cache.get("proj-1")

        assert result is None


class TestMget:
    @pytest.mark.asyncio
    async def test_mget_all_hits(self, redis) -> None:
        await redis.set(f"{CACHE_PREFIX}:p1:cumulative", json.dumps({"a": 1}))
        await redis.set(f"{CACHE_PREFIX}:p2:cumulative", json.dumps({"b": 2}))
        cache = _make_cache(redis)

        result = await cache.mget(["p1", "p2"], "cumulative")

        assert result == {"p1": {"a": 1}, "p2": {"b": 2}}

    @pytest.mark.asyncio
    async def test_mget_partial_miss(self, redis) -> None:
        await redis.set(f"{CACHE_PREFIX}:p1:cumulative", json.dumps({"a": 1}))
        cache = _make_cache(redis)

        result = await cache.mget(["p1", "p2"])

        assert result["p1"] == {"a": 1}
        assert result["p2"] is None

    @pytest.mark.asyncio
    async def test_mget_empty_list(self, redis) -> None:
        cache = _make_cache(redis)

        result = await cache.mget([])

        assert result == {}

    @pytest.mark.asyncio
    async def test_mget_redis_error(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.mget.side_effect = ConnectionError("Redis down")
        cache = _make_cache(mock_redis)

        result = await cache.mget(["p1", "p2"])

        assert result == {"p1": None, "p2": None}


class TestSet:
    @pytest.mark.asyncio
    async def test_set_stores_json(self, redis) -> None:
        cache = _make_cache(redis)

        await cache.set("proj-1", SAMPLE_SCORES, "cumulative")

        raw = await redis.get(f"{CACHE_PREFIX}:proj-1:cumulative")
        assert json.loads(raw) == SAMPLE_SCORES

    @pytest.mark.asyncio
    async def test_set_applies_ttl(self, redis) -> None:
        cache = _make_cache(redis)

        await cache.set("proj-1", SAMPLE_SCORES, "cumulative")

        ttl = await redis.ttl(f"{CACHE_PREFIX}:proj-1:cumulative")
        assert 0 < ttl <= CACHE_TTL

    @pytest.mark.asyncio
    async def test_set_redis_error_silent(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.set.side_effect = ConnectionError("Redis down")
        cache = _make_cache(mock_redis)

        await cache.set("proj-1", SAMPLE_SCORES)


class TestInvalidate:
    @pytest.mark.asyncio
    async def test_invalidate_deletes_both_types(self, redis) -> None:
        cumulative_key = f"{CACHE_PREFIX}:proj-1:cumulative"
        punctual_key = f"{CACHE_PREFIX}:proj-1:punctual"
        await redis.set(cumulative_key, json.dumps(SAMPLE_SCORES))
        await redis.set(punctual_key, json.dumps(SAMPLE_SCORES))
        cache = _make_cache(redis)

        await cache.invalidate("proj-1")

        assert await redis.get(cumulative_key) is None
        assert await redis.get(punctual_key) is None

    @pytest.mark.asyncio
    async def test_invalidate_redis_error_silent(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = ConnectionError("Redis down")
        cache = _make_cache(mock_redis)

        await cache.invalidate("proj-1")


class TestInvalidateAll:
    @pytest.mark.asyncio
    async def test_invalidate_all_scans_and_deletes(self, redis) -> None:
        keys = [
            f"{CACHE_PREFIX}:p1:cumulative",
            f"{CACHE_PREFIX}:p2:cumulative",
            f"{CACHE_PREFIX}:p3:punctual",
        ]
        for key in keys:
            await redis.set(key, json.dumps({"data": True}))
        cache = _make_cache(redis)

        await cache.invalidate_all()

        for key in keys:
            assert await redis.get(key) is None

    @pytest.mark.asyncio
    async def test_invalidate_all_ignores_unrelated_keys(self, redis) -> None:
        cache_key = f"{CACHE_PREFIX}:p1:cumulative"
        unrelated_key = "other:key"
        await redis.set(cache_key, json.dumps({"data": True}))
        await redis.set(unrelated_key, "keep me")
        cache = _make_cache(redis)

        await cache.invalidate_all()

        assert await redis.get(cache_key) is None
        assert await redis.get(unrelated_key) == "keep me"

    @pytest.mark.asyncio
    async def test_invalidate_all_redis_error_silent(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.scan.side_effect = ConnectionError("Redis down")
        cache = _make_cache(mock_redis)

        await cache.invalidate_all()
