"""Tests for the read-only Copper Developer API client."""

import json

import httpx
import pytest

from app.core.services.copper_client import (
    COPPER_PROVIDER,
    COPPER_USER_EMAIL_KEY,
    OPPORTUNITY_STATUS_OPEN,
    OPPORTUNITY_STATUS_WON,
    CopperAuthError,
    CopperClient,
    CopperError,
)
from app.core.services.integration_token_service import IntegrationTokenService


def _client(handler) -> CopperClient:
    return CopperClient(
        api_key="k-123", user_email="owner@example.com", transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_requests_carry_copper_auth_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": 1, "name": "Vizzuality"})

    async with _client(handler) as copper:
        account = await copper.get_account()

    assert account["name"] == "Vizzuality"
    req = seen[0]
    assert str(req.url) == "https://api.copper.com/developer_api/v1/account"
    assert req.headers["X-PW-AccessToken"] == "k-123"
    assert req.headers["X-PW-UserEmail"] == "owner@example.com"
    assert req.headers["X-PW-Application"] == "developer_api"


@pytest.mark.asyncio
async def test_rejected_credentials_raise_auth_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "authentication error"})

    async with _client(handler) as copper:
        with pytest.raises(CopperAuthError):
            await copper.get_account()


@pytest.mark.asyncio
async def test_search_opportunities_pages_until_a_short_page() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        size = 200 if body["page_number"] == 1 else 3
        start = (body["page_number"] - 1) * 200
        return httpx.Response(200, json=[{"id": start + i} for i in range(size)])

    async with _client(handler) as copper:
        opps = await copper.search_opportunities(
            pipeline_stage_ids=[124540], status_ids=[OPPORTUNITY_STATUS_OPEN]
        )

    assert len(opps) == 203
    assert [b["page_number"] for b in bodies] == [1, 2]
    assert bodies[0]["pipeline_stage_ids"] == [124540]
    assert bodies[0]["status_ids"] == [OPPORTUNITY_STATUS_OPEN]
    assert bodies[0]["page_size"] == 200


@pytest.mark.asyncio
async def test_client_exposes_no_write_operations() -> None:
    # The API key carries full write access to the CRM; the client must stay read-only.
    write_verbs = ("create", "update", "delete", "put", "patch", "remove", "add")
    public = [name for name in dir(CopperClient) if not name.startswith("_")]
    assert not [name for name in public if name.startswith(write_verbs)]


@pytest.mark.asyncio
async def test_from_db_is_none_until_key_and_email_are_stored(db_session) -> None:
    assert await CopperClient.from_db(db_session) is None

    await IntegrationTokenService.save_token(
        db_session, provider=COPPER_PROVIDER, token="k-123", token_type="api_key"
    )
    assert await CopperClient.from_db(db_session) is None

    await IntegrationTokenService.set_setting(
        db_session, COPPER_PROVIDER, COPPER_USER_EMAIL_KEY, "owner@example.com"
    )
    copper = await CopperClient.from_db(db_session)
    assert copper is not None
    async with copper:
        assert copper._http.headers["X-PW-AccessToken"] == "k-123"


@pytest.mark.asyncio
async def test_network_failures_surface_as_copper_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    async with _client(handler) as copper:
        with pytest.raises(CopperError):
            await copper.get_account()


@pytest.mark.asyncio
async def test_search_opportunities_can_bound_the_stage_change_date() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=[])

    async with _client(handler) as copper:
        await copper.search_opportunities(
            pipeline_stage_ids=[124566],
            status_ids=[OPPORTUNITY_STATUS_WON],
            minimum_stage_change_date=1_700_000_000,
        )

    assert bodies[0]["status_ids"] == [OPPORTUNITY_STATUS_WON]
    assert bodies[0]["minimum_stage_change_date"] == 1_700_000_000
