"""Tests for request ID middleware."""

import re

import pytest
from httpx import AsyncClient


UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
)


class TestRequestIDMiddleware:

    @pytest.mark.asyncio
    async def test_response_contains_x_request_id(self, client: AsyncClient) -> None:
        response = await client.get("/health/live")
        assert "x-request-id" in response.headers
        assert UUID4_PATTERN.match(response.headers["x-request-id"])

    @pytest.mark.asyncio
    async def test_propagates_client_request_id(self, client: AsyncClient) -> None:
        response = await client.get(
            "/health/live",
            headers={"X-Request-ID": "custom-id-123"},
        )
        assert response.headers["x-request-id"] == "custom-id-123"

    @pytest.mark.asyncio
    async def test_generates_unique_ids(self, client: AsyncClient) -> None:
        r1 = await client.get("/health/live")
        r2 = await client.get("/health/live")
        assert r1.headers["x-request-id"] != r2.headers["x-request-id"]
