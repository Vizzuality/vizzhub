"""Unit tests for ScoreCacheService."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.score_cache import CACHE_PREFIX, CACHE_TTL, ScoreCacheService


def _make_cache(redis_mock: AsyncMock) -> ScoreCacheService:
    return ScoreCacheService(redis_mock)


SAMPLE_SCORES = {
    "indicators": {"p_time": 0.85, "p_cost": 0.9},
    "scores": {"score": 75.0, "dimensions": {}},
}


class TestGet:
    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        redis = AsyncMock()
        redis.get.return_value = json.dumps(SAMPLE_SCORES)
        cache = _make_cache(redis)

        result = await cache.get("proj-1", "cumulative")

        assert result == SAMPLE_SCORES
        redis.get.assert_awaited_once_with(f"{CACHE_PREFIX}:proj-1:cumulative")

    @pytest.mark.asyncio
    async def test_cache_miss(self) -> None:
        redis = AsyncMock()
        redis.get.return_value = None
        cache = _make_cache(redis)

        result = await cache.get("proj-1")

        assert result is None

    @pytest.mark.asyncio
    async def test_redis_error_returns_none(self) -> None:
        redis = AsyncMock()
        redis.get.side_effect = ConnectionError("Redis down")
        cache = _make_cache(redis)

        result = await cache.get("proj-1")

        assert result is None


class TestMget:
    @pytest.mark.asyncio
    async def test_mget_all_hits(self) -> None:
        redis = AsyncMock()
        data_a = json.dumps({"a": 1})
        data_b = json.dumps({"b": 2})
        redis.mget.return_value = [data_a, data_b]
        cache = _make_cache(redis)

        result = await cache.mget(["p1", "p2"], "cumulative")

        assert result == {"p1": {"a": 1}, "p2": {"b": 2}}

    @pytest.mark.asyncio
    async def test_mget_partial_miss(self) -> None:
        redis = AsyncMock()
        redis.mget.return_value = [json.dumps({"a": 1}), None]
        cache = _make_cache(redis)

        result = await cache.mget(["p1", "p2"])

        assert result["p1"] == {"a": 1}
        assert result["p2"] is None

    @pytest.mark.asyncio
    async def test_mget_empty_list(self) -> None:
        redis = AsyncMock()
        cache = _make_cache(redis)

        result = await cache.mget([])

        assert result == {}
        redis.mget.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mget_redis_error(self) -> None:
        redis = AsyncMock()
        redis.mget.side_effect = ConnectionError("Redis down")
        cache = _make_cache(redis)

        result = await cache.mget(["p1", "p2"])

        assert result == {"p1": None, "p2": None}


class TestSet:
    @pytest.mark.asyncio
    async def test_set_stores_json(self) -> None:
        redis = AsyncMock()
        cache = _make_cache(redis)

        await cache.set("proj-1", SAMPLE_SCORES, "cumulative")

        redis.set.assert_awaited_once_with(
            f"{CACHE_PREFIX}:proj-1:cumulative",
            json.dumps(SAMPLE_SCORES),
            ex=CACHE_TTL,
        )

    @pytest.mark.asyncio
    async def test_set_redis_error_silent(self) -> None:
        redis = AsyncMock()
        redis.set.side_effect = ConnectionError("Redis down")
        cache = _make_cache(redis)

        await cache.set("proj-1", SAMPLE_SCORES)


class TestInvalidate:
    @pytest.mark.asyncio
    async def test_invalidate_deletes_both_types(self) -> None:
        redis = AsyncMock()
        cache = _make_cache(redis)

        await cache.invalidate("proj-1")

        redis.delete.assert_awaited_once_with(
            f"{CACHE_PREFIX}:proj-1:cumulative",
            f"{CACHE_PREFIX}:proj-1:punctual",
        )

    @pytest.mark.asyncio
    async def test_invalidate_redis_error_silent(self) -> None:
        redis = AsyncMock()
        redis.delete.side_effect = ConnectionError("Redis down")
        cache = _make_cache(redis)

        await cache.invalidate("proj-1")


class TestInvalidateAll:
    @pytest.mark.asyncio
    async def test_invalidate_all_scans_and_deletes(self) -> None:
        redis = AsyncMock()
        keys = [f"{CACHE_PREFIX}:p1:cumulative", f"{CACHE_PREFIX}:p2:cumulative"]
        redis.scan.return_value = (0, keys)
        cache = _make_cache(redis)

        await cache.invalidate_all()

        redis.scan.assert_awaited_once()
        redis.delete.assert_awaited_once_with(*keys)

    @pytest.mark.asyncio
    async def test_invalidate_all_multiple_pages(self) -> None:
        redis = AsyncMock()
        keys1 = [f"{CACHE_PREFIX}:p1:cumulative"]
        keys2 = [f"{CACHE_PREFIX}:p2:cumulative"]
        redis.scan.side_effect = [
            (42, keys1),
            (0, keys2),
        ]
        cache = _make_cache(redis)

        await cache.invalidate_all()

        assert redis.delete.await_count == 2

    @pytest.mark.asyncio
    async def test_invalidate_all_redis_error_silent(self) -> None:
        redis = AsyncMock()
        redis.scan.side_effect = ConnectionError("Redis down")
        cache = _make_cache(redis)

        await cache.invalidate_all()
