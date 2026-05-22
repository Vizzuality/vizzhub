"""HTTP tests for /api/accrual/cells and /api/accrual/projects/{id}/*."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB

_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    """Seed the synthetic dev user so created_by FK never fires (period creation needs it)."""
    result = await db_session.execute(select(UserDB).where(UserDB.id == _DEV_USER_ID))
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=_DEV_USER_ID, email="dev@test.com"))
        await db_session.flush()


@pytest.mark.asyncio
async def test_get_project_cells_empty(client: AsyncClient) -> None:
    p = await client.post(
        "/api/projects", json={"name": "A", "code": "TEST.AC.GET1", "currency": "USD"}
    )
    pid = p.json()["id"]
    resp = await client.get(f"/api/accrual/projects/{pid}/cells")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_redistribute_endpoint_creates_cells(client: AsyncClient) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01", "fx_rates": {"USD": "1.10"}},
    )
    p = await client.post(
        "/api/projects",
        json={
            "name": "A",
            "code": "TEST.AC.RD1",
            "currency": "USD",
            "budget": 1200,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    pid = p.json()["id"]
    resp = await client.post(f"/api/accrual/projects/{pid}/redistribute", json={})
    assert resp.status_code == 200
    assert resp.json()["cells_updated"] == 12

    cells = (await client.get(f"/api/accrual/projects/{pid}/cells")).json()
    assert len(cells) == 12
    for cell in cells:
        assert cell["is_manual_override"] is False
        assert cell["is_frozen"] is False


@pytest.mark.asyncio
async def test_patch_cell_sets_override(client: AsyncClient) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01", "fx_rates": {"USD": "1.10"}},
    )
    p = await client.post(
        "/api/projects",
        json={
            "name": "A",
            "code": "TEST.AC.PATCH1",
            "currency": "USD",
            "budget": 1200,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    pid = p.json()["id"]
    await client.post(f"/api/accrual/projects/{pid}/redistribute", json={})
    cells = (await client.get(f"/api/accrual/projects/{pid}/cells")).json()
    target = next(c for c in cells if c["month"] == 5)

    resp = await client.patch(f"/api/accrual/cells/{target['id']}", json={"amount": 250})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert Decimal(body["amount"]) == Decimal("250.00")
    assert body["is_manual_override"] is True


@pytest.mark.asyncio
async def test_patch_frozen_cell_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01", "fx_rates": {"USD": "1.10"}},
    )
    p = await client.post(
        "/api/projects",
        json={
            "name": "A",
            "code": "TEST.AC.FRZ1",
            "currency": "USD",
            "budget": 1200,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    pid = p.json()["id"]
    await client.post(f"/api/accrual/projects/{pid}/redistribute", json={})
    cells = (await client.get(f"/api/accrual/projects/{pid}/cells")).json()
    target = next(c for c in cells if c["month"] == 5)

    res = await db_session.execute(
        select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.id == UUID(target["id"]))
    )
    cell = res.scalar_one()
    cell.is_frozen = True
    cell.frozen_at = datetime.now(UTC)
    cell.frozen_rate = Decimal("1.10")
    cell.frozen_eur_amount = Decimal("90.91")
    await db_session.commit()

    resp = await client.patch(f"/api/accrual/cells/{target['id']}", json={"amount": 999})
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_patch_cell_negative_amount_returns_400(client: AsyncClient) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01", "fx_rates": {"USD": "1.10"}},
    )
    p = await client.post(
        "/api/projects",
        json={
            "name": "A",
            "code": "TEST.AC.NEG1",
            "currency": "USD",
            "budget": 1200,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    pid = p.json()["id"]
    await client.post(f"/api/accrual/projects/{pid}/redistribute", json={})
    cells = (await client.get(f"/api/accrual/projects/{pid}/cells")).json()

    resp = await client.patch(
        f"/api/accrual/cells/{cells[0]['id']}",
        json={"amount": -10},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_delete_override_clears_and_redistributes(client: AsyncClient) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01", "fx_rates": {"USD": "1.10"}},
    )
    p = await client.post(
        "/api/projects",
        json={
            "name": "A",
            "code": "TEST.AC.CLR1",
            "currency": "USD",
            "budget": 1200,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    pid = p.json()["id"]
    await client.post(f"/api/accrual/projects/{pid}/redistribute", json={})
    cells = (await client.get(f"/api/accrual/projects/{pid}/cells")).json()
    target = next(c for c in cells if c["month"] == 5)
    await client.patch(f"/api/accrual/cells/{target['id']}", json={"amount": 300})

    resp = await client.delete(f"/api/accrual/cells/{target['id']}/override")
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_manual_override"] is False
    assert Decimal(resp.json()["amount"]) == Decimal("100.00")


@pytest.mark.asyncio
async def test_bulk_cells_happy_path(client: AsyncClient) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01", "fx_rates": {"USD": "1.10"}},
    )
    p = await client.post(
        "/api/projects",
        json={
            "name": "A",
            "code": "TEST.AC.BLK1",
            "currency": "USD",
            "budget": 1200,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    pid = p.json()["id"]

    resp = await client.post(
        "/api/accrual/cells/bulk",
        json={
            "updates": [
                {"project_id": pid, "year": 2026, "month": 2, "amount": 150},
                {"project_id": pid, "year": 2026, "month": 3, "amount": 200},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 2
