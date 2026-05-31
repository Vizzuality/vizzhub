"""Tests for the original_budget field on ProjectDB (Task 4.0)."""

from decimal import Decimal

import pytest

from app.core.models.project import ProjectDB


@pytest.mark.asyncio
async def test_original_budget_round_trip_via_orm(db_session):
    p = ProjectDB(name="t", code="ORIG-1", status="live", original_budget=Decimal("12345.67"))
    db_session.add(p)
    await db_session.flush()
    await db_session.refresh(p)
    assert p.original_budget == Decimal("12345.67")


@pytest.mark.asyncio
async def test_original_budget_in_get_response(client, db_session):
    p = ProjectDB(name="t", code="ORIG-2", status="live", original_budget=Decimal("999.00"))
    db_session.add(p)
    await db_session.flush()
    r = await client.get(f"/api/projects/{p.id}")
    assert r.status_code == 200
    # VizzHub serialises Decimal as a JSON string (gotcha_pydantic-decimal-serialization.md)
    body = r.json()
    assert "original_budget" in body
    assert Decimal(body["original_budget"]) == Decimal("999.00")


@pytest.mark.asyncio
async def test_original_budget_writable_via_patch(client, db_session):
    # Task 6 wired original_budget into PATCHABLE_FIELDS so it flows through the
    # accrual provisioning path. A non-derivable project (no currency rate / dates)
    # persists the raw original_budget without deriving budget.
    p = ProjectDB(name="t", code="ORIG-3", status="live")
    db_session.add(p)
    await db_session.flush()
    r = await client.patch(f"/api/projects/{p.id}", json={"original_budget": "500.00"})
    assert r.status_code == 200
    await db_session.refresh(p)
    assert p.original_budget == Decimal("500.00")
