"""HTTP tests for /api/accrual/lines CRUD and project links."""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.user import UserDB
from app.database import get_db
from app.main import app
from app.modules.accrual.models.accrual_cell import AccrualCellDB, CellSource
from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from tests.conftest import DEFAULT_PROGRAM_ID


@pytest.fixture(autouse=True)
def _seed_program(default_program: str) -> None:
    """Projects require a program on create; seed the shared one for every test."""


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
        json={
            "program_id": DEFAULT_PROGRAM_ID,
            "name": f"P {code}",
            "code": code,
            "currency": "USD",
        },
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
    create = await client.post(
        "/api/accrual/lines", json={"program_id": DEFAULT_PROGRAM_ID, "name": "L", "value_eur": 50}
    )
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
        json={"program_id": DEFAULT_PROGRAM_ID, "name": "Old", "value_eur": 100, "currency": "USD"},
    )
    line_id = create.json()["id"]

    resp = await client.patch(
        f"/api/accrual/lines/{line_id}",
        json={
            "program_id": DEFAULT_PROGRAM_ID,
            "name": "Renamed",
            "value_eur": 999,
            "window_start": "2027-01-01",
        },
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
        json={"program_id": DEFAULT_PROGRAM_ID, "name": "X"},
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
    create = await client.post(
        "/api/accrual/lines", json={"program_id": DEFAULT_PROGRAM_ID, "name": "L", "value_eur": 100}
    )
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
    create = await client.post(
        "/api/accrual/lines", json={"program_id": DEFAULT_PROGRAM_ID, "name": "L", "value_eur": 100}
    )
    line_id = create.json()["id"]
    pid = await _make_project(client, "TEST.LN.UNL1")
    resp = await client.delete(f"/api/accrual/lines/{line_id}/projects/{pid}")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_patch_line_sets_rate_override(client: AsyncClient) -> None:
    """Setting rate recomputes value_eur = value_orig / rate and persists the override."""
    create = await client.post(
        "/api/accrual/lines",
        json={
            "name": "USD grant",
            "value_eur": 0,
            "value_orig": "1080",
            "currency": "USD",
            "window_start": "2026-01-01",
            "window_end": "2026-03-31",
        },
    )
    assert create.status_code == 201, create.text
    line_id = create.json()["id"]

    resp = await client.patch(f"/api/accrual/lines/{line_id}", json={"rate": "1.08"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rate"] is not None
    assert Decimal(body["rate"]) == Decimal("1.08")
    assert Decimal(body["value_eur"]) == Decimal("1000.00")


@pytest.mark.asyncio
async def test_patch_line_clears_rate(client: AsyncClient) -> None:
    """Sending rate=null clears the override; the stored rate field becomes null."""
    # Seed a period with a USD rate so resolve_rate succeeds on clear.
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01", "fx_rates": {"USD": "1.20"}},
    )

    create = await client.post(
        "/api/accrual/lines",
        json={
            "name": "USD grant clear",
            "value_eur": 0,
            "value_orig": "1200",
            "currency": "USD",
            "window_start": "2026-01-01",
            "window_end": "2026-03-31",
        },
    )
    assert create.status_code == 201, create.text
    line_id = create.json()["id"]

    # First set an override rate.
    set_resp = await client.patch(f"/api/accrual/lines/{line_id}", json={"rate": "1.08"})
    assert set_resp.status_code == 200
    assert set_resp.json()["rate"] is not None

    # Now clear it: rate=null reverts to period rate (1.20) for value_eur recomputation.
    clear_resp = await client.patch(f"/api/accrual/lines/{line_id}", json={"rate": None})
    assert clear_resp.status_code == 200, clear_resp.text
    assert clear_resp.json()["rate"] is None


@pytest.mark.asyncio
async def test_patch_line_rejects_non_positive_rate(client: AsyncClient) -> None:
    """A rate of 0 (or negative) must be rejected with 400 (Pydantic → global handler)."""
    create = await client.post(
        "/api/accrual/lines", json={"program_id": DEFAULT_PROGRAM_ID, "name": "L", "value_eur": 100}
    )
    assert create.status_code == 201, create.text
    line_id = create.json()["id"]

    resp = await client.patch(f"/api/accrual/lines/{line_id}", json={"rate": "0"})
    assert resp.status_code == 400, resp.text


def _year_total(summary: dict) -> Decimal:
    return sum((Decimal(str(m["amount_eur"])) for m in summary["months"]), Decimal("0"))


@pytest.mark.asyncio
async def test_update_line_window_moves_cells_and_clears_dashboard(client: AsyncClient) -> None:
    """Moving a line's window relocates its cells: the old year drops to zero in the
    dashboard (no orphaned cells) and the new year carries the value. Regression for
    the phantom-recognition bug where the grid hid the moved row but the dashboard
    kept summing its old cells."""
    await client.post("/api/accrual/periods", json={"start_date": "2026-01-01"})
    create = await client.post(
        "/api/accrual/lines",
        json={
            "name": "Mover",
            "value_eur": 1200,
            "currency": "EUR",
            "window_start": "2026-01-01",
            "window_end": "2026-12-01",
        },
    )
    line_id = create.json()["id"]
    assert (
        await client.post(f"/api/accrual/lines/{line_id}/redistribute", json={})
    ).status_code == 200

    before = (await client.get("/api/accrual/dashboard/summary", params={"year": 2026})).json()
    assert _year_total(before) == Decimal("1200.00")

    patch = await client.patch(
        f"/api/accrual/lines/{line_id}",
        json={"window_start": "2024-01-01", "window_end": "2024-12-01"},
    )
    assert patch.status_code == 200, patch.text

    after_2026 = (await client.get("/api/accrual/dashboard/summary", params={"year": 2026})).json()
    after_2024 = (await client.get("/api/accrual/dashboard/summary", params={"year": 2024})).json()
    assert _year_total(after_2026) == Decimal("0")
    assert _year_total(after_2024) == Decimal("1200.00")


@pytest.mark.asyncio
async def test_update_line_window_rejects_frozen_orphan(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A window move that would orphan a frozen (recognised) cell is rejected with 409.

    Production atomicity (the window change reverts on the 409) is guaranteed by
    ``get_db`` rolling back on exception; the test harness shares one session and
    cannot replicate that rollback, so we assert only the 409 contract here."""
    from datetime import datetime

    await client.post("/api/accrual/periods", json={"start_date": "2026-01-01"})
    create = await client.post(
        "/api/accrual/lines",
        json={
            "name": "Frozen",
            "value_eur": 1200,
            "currency": "EUR",
            "window_start": "2026-01-01",
            "window_end": "2026-12-01",
        },
    )
    line_id = create.json()["id"]
    await client.post(f"/api/accrual/lines/{line_id}/redistribute", json={})

    cell = (
        await db_session.execute(
            select(AccrualCellDB).where(
                AccrualCellDB.line_id == UUID(line_id), AccrualCellDB.month == 3
            )
        )
    ).scalar_one()
    cell.is_frozen = True
    cell.frozen_at = datetime(2026, 4, 1, tzinfo=UTC)
    cell.frozen_eur_amount = cell.amount
    await db_session.commit()

    resp = await client.patch(
        f"/api/accrual/lines/{line_id}",
        json={"window_start": "2024-01-01", "window_end": "2024-12-01"},
    )
    assert resp.status_code == 409, resp.text
    assert "frozen" in resp.json()["detail"].lower()


async def _line_with_frozen_2026(db: AsyncSession) -> AccrualLineDB:
    line = AccrualLineDB(
        name="Repair line",
        source=LineSource.MANUAL.value,
        value_eur=Decimal("1200"),
        window_start=datetime(2026, 1, 1).date(),
        window_end=datetime(2026, 12, 1).date(),
    )
    db.add(line)
    await db.flush()
    for m in range(1, 13):
        db.add(
            AccrualCellDB(
                line_id=line.id,
                year=2026,
                month=m,
                amount=Decimal("100"),
                source=CellSource.MANUAL.value,
            )
        )
    await db.flush()
    frozen = (
        await db.execute(
            select(AccrualCellDB).where(AccrualCellDB.line_id == line.id, AccrualCellDB.month == 3)
        )
    ).scalar_one()
    frozen.is_frozen = True
    frozen.frozen_at = datetime(2026, 4, 1, tzinfo=UTC)
    frozen.frozen_eur_amount = frozen.amount
    await db.commit()
    return line


@pytest_asyncio.fixture
async def manager_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    async def override_user() -> TokenData:
        return TokenData(
            user_id=str(uuid4()),
            email="mgr@example.com",
            roles=["mgr"],
            permissions=["accrual:view", "accrual:manage"],
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_window_move_with_frozen_orphan_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    line = await _line_with_frozen_2026(db_session)
    resp = await client.patch(
        f"/api/accrual/lines/{line.id}",
        json={"window_start": "2024-01-01", "window_end": "2024-12-01"},
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_patch_window_move_include_frozen_succeeds(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    line = await _line_with_frozen_2026(db_session)
    resp = await client.patch(
        f"/api/accrual/lines/{line.id}",
        json={
            "window_start": "2024-01-01",
            "window_end": "2024-12-01",
            "include_frozen": True,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["window_start"] == "2024-01-01"


@pytest.mark.asyncio
async def test_patch_window_move_include_frozen_requires_period_manage(
    manager_client: AsyncClient, db_session: AsyncSession
) -> None:
    line = await _line_with_frozen_2026(db_session)
    resp = await manager_client.patch(
        f"/api/accrual/lines/{line.id}",
        json={
            "window_start": "2024-01-01",
            "window_end": "2024-12-01",
            "include_frozen": True,
        },
    )
    assert resp.status_code == 403, resp.text
