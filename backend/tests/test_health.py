"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


class TestLiveness:
    @pytest.mark.asyncio
    async def test_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestReadiness:
    @pytest.mark.asyncio
    async def test_returns_check_structure(self, client: AsyncClient) -> None:
        response = await client.get("/health/ready")
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "redis" in data["checks"]
        assert "worker" in data["checks"]
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_redis_shows_unavailable_without_redis(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.get("/health/ready")
        data = response.json()
        assert data["checks"]["redis"]["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_worker_shows_unavailable_without_redis(
        self,
        client: AsyncClient,
    ) -> None:
        response = await client.get("/health/ready")
        data = response.json()
        assert data["checks"]["worker"]["status"] == "unavailable"
