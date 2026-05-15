"""Invalidate the entire score cache in Redis.

Use after a deploy that changes how scores are computed. The cache has
a 1h TTL safety net but you usually don't want to wait — calling this
forces the next read to recompute from MetricsDB with the new logic.

Usage (production via docker exec):
    docker exec hub-backend python scripts/invalidate_score_cache.py
"""

import asyncio
import os
import sys

from app.modules.scorecard.services.score_cache import create_score_cache


async def main() -> int:
    host = os.environ.get("REDIS_HOST", "redis")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    password = os.environ.get("REDIS_PASSWORD", "")

    redis_client, cache = await create_score_cache(host, port, password)
    if cache is None or redis_client is None:
        print("Redis not available — nothing to invalidate.")
        return 1

    try:
        await cache.invalidate_all()
        print(f"Invalidated all score cache keys at {host}:{port}.")
        return 0
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
