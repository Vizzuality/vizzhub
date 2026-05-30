"""HTTP tests for /api/accrual/lines CRUD and project links."""

from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.accrual.models.accrual_cell import AccrualCellDB, CellSource
from app.modules.accrual.models.accrual_line import AccrualLineDB
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB

_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    result = await db_session.execute(select(UserDB).where(UserDB.id == _DEV_USER_ID))
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=_DEV_USER_ID, email="dev@test.com"))
        await db_session.flush()


async def _make_project(client: AsyncClient, code: str) -> str:
    resp = await client.post(
        "/api/projects",
        json={"name": f"P {code}", "code": code, "currency": "USD"},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_line_manual_with_projects(client: AsyncClient) -> None:
    pid = await _make_project(client, "TEST.LN.CR1")
    resp = await client.post(
        "/api/accrual/lines",
        json={
            "name": "New grant",
            "value_eur": 12000,
            "currency": "EUR",
            "window_start": "2026-01-01",
            "window_end": "2026-12-01",
            "project_ids": [pid],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "New grant"
    assert body["source"] == "manual"
    assert Decimal(body["value_eur"]) == Decimal("12000")
    assert [p["id"] for p in body["projects"]] == [pid]


@pytest.mark.asyncio
async def test_create_line_window_validation(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/accrual/lines",
        json={"value_eur": 100, "window_start": "2026-12-01", "window_end": "2026-01-01"},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_get_line_detail_and_404(client: AsyncClient) -> None:
    create = await client.post("/api/accrual/lines", json={"name": "L", "value_eur": 50})
    line_id = create.json()["id"]
    ok = await client.get(f"/api/accrual/lines/{line_id}")
    assert ok.status_code == 200
    assert ok.json()["id"] == line_id

    missing = await client.get("/api/accrual/lines/00000000-0000-0000-0000-0000000000ff")
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_update_line_partial(client: AsyncClient) -> None:
    create = await client.post(
        "/api/accrual/lines",
        json={"name": "Old", "value_eur": 100, "currency": "USD"},
    )
    line_id = create.json()["id"]

    resp = await client.patch(
        f"/api/accrual/lines/{line_id}",
        json={"name": "Renamed", "value_eur": 999, "window_start": "2027-01-01"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Renamed"
    assert Decimal(body["value_eur"]) == Decimal("999")
    assert body["window_start"] == "2027-01-01"
    # currency was not in the payload → untouched
    assert body["currency"] == "USD"


@pytest.mark.asyncio
async def test_update_line_window_validation(client: AsyncClient) -> None:
    create = await client.post("/api/accrual/lines", json={"value_eur": 100})
    line_id = create.json()["id"]
    resp = await client.patch(
        f"/api/accrual/lines/{line_id}",
        json={"window_start": "2026-12-01", "window_end": "2026-01-01"},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_update_line_404(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/accrual/lines/00000000-0000-0000-0000-0000000000ff",
        json={"name": "X"},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_delete_line_cascades_cells(client: AsyncClient, db_session: AsyncSession) -> None:
    create = await client.post(
        "/api/accrual/lines",
        json={
            "name": "L",
            "value_eur": 100,
            "window_start": "2026-01-01",
            "window_end": "2026-12-01",
        },
    )
    line_id = UUID(create.json()["id"])
    db_session.add(
        AccrualCellDB(
            line_id=line_id,
            year=2026,
            month=1,
            amount=Decimal("10"),
            source=CellSource.MANUAL.value,
        )
    )
    await db_session.commit()

    resp = await client.delete(f"/api/accrual/lines/{line_id}")
    assert resp.status_code == 204, resp.text

    remaining = await db_session.execute(
        select(AccrualCellDB).where(AccrualCellDB.line_id == line_id)
    )
    assert remaining.scalars().all() == []
    gone = await db_session.execute(select(AccrualLineDB).where(AccrualLineDB.id == line_id))
    assert gone.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_line_404(client: AsyncClient) -> None:
    resp = await client.delete("/api/accrual/lines/00000000-0000-0000-0000-0000000000ff")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_link_and_unlink_project(client: AsyncClient, db_session: AsyncSession) -> None:
    create = await client.post("/api/accrual/lines", json={"name": "L", "value_eur": 100})
    line_id = create.json()["id"]
    pid = await _make_project(client, "TEST.LN.LNK1")

    linked = await client.post(f"/api/accrual/lines/{line_id}/projects", json={"project_id": pid})
    assert linked.status_code == 201, linked.text
    assert [p["id"] for p in linked.json()["projects"]] == [pid]

    # Idempotent: linking again does not duplicate.
    await client.post(f"/api/accrual/lines/{line_id}/projects", json={"project_id": pid})
    count = await db_session.execute(
        select(AccrualLineProjectDB).where(AccrualLineProjectDB.line_id == UUID(line_id))
    )
    assert len(count.scalars().all()) == 1

    unlinked = await client.delete(f"/api/accrual/lines/{line_id}/projects/{pid}")
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["projects"] == []


@pytest.mark.asyncio
async def test_unlink_project_not_linked_404(client: AsyncClient) -> None:
    create = await client.post("/api/accrual/lines", json={"name": "L", "value_eur": 100})
    line_id = create.json()["id"]
    pid = await _make_project(client, "TEST.LN.UNL1")
    resp = await client.delete(f"/api/accrual/lines/{line_id}/projects/{pid}")
    assert resp.status_code == 404, resp.text
