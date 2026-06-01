"""API tests for the accrual dashboard summary endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_summary_returns_well_formed_payload_for_empty_year(
    client: AsyncClient,
) -> None:
    resp = await client.get("/api/accrual/dashboard/summary", params={"year": 2026})
    assert resp.status_code == 200
    body = resp.json()
    assert body["year"] == 2026
    assert len(body["months"]) == 12
    assert {
        "recognized_ytd_eur",
        "recognized_quarter_eur",
        "contracted_total_eur",
        "backlog_eur",
        "plan_recognized_pct",
    } <= set(body["kpis"].keys())
    assert isinstance(body["available_years"], list)


@pytest.mark.asyncio
async def test_summary_rejects_non_integer_year(client: AsyncClient) -> None:
    resp = await client.get("/api/accrual/dashboard/summary", params={"year": "abc"})
    assert resp.status_code == 400
