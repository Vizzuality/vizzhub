"""HTTP tests for /api/accrual/cells and /api/accrual/projects/{id}/*."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from app.modules.accrual.models.project_accrual_cell import CellSource, ProjectAccrualCellDB

_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def _make_line(
    db: AsyncSession,
    *,
    value_eur: str = "1200",
    source: LineSource = LineSource.EXCEL,
    excel_code: str | None = None,
    name: str = "Line",
    currency: str | None = None,
    window_start=None,
    window_end=None,
    cells: list[tuple[int, int, str]] | None = None,
    project_ids: list[UUID] | None = None,
) -> AccrualLineDB:
    """Insert a line directly (no line-creation endpoint exists until fase 2).

    The grid is line-derived now, so tests build their rows here rather than via
    the legacy project+redistribute flow (which writes project-keyed cells with
    no line_id and is invisible to the grid).
    """
    line = AccrualLineDB(
        name=name,
        source=source.value,
        excel_code=excel_code,
        value_eur=Decimal(value_eur),
        currency=currency,
        window_start=window_start,
        window_end=window_end,
    )
    db.add(line)
    await db.flush()
    project_ids = project_ids or []
    for pid in project_ids:
        db.add(AccrualLineProjectDB(line_id=line.id, project_id=pid))
    single_pid = project_ids[0] if len(project_ids) == 1 else None
    for year, month, amount in cells or []:
        db.add(
            ProjectAccrualCellDB(
                line_id=line.id,
                project_id=single_pid,
                year=year,
                month=month,
                amount=Decimal(amount),
                source=CellSource.EXCEL.value,
            )
        )
    await db.flush()
    return line


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
async def test_redistribute_endpoint_creates_cells(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01"},
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
        # Cells are EUR; eur_amount mirrors amount.
        assert cell["eur_amount"] == cell["amount"]


@pytest.mark.asyncio
async def test_patch_cell_sets_override(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01"},
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
        json={"start_date": "2026-01-01"},
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
    cell.frozen_eur_amount = cell.amount
    await db_session.commit()

    resp = await client.patch(f"/api/accrual/cells/{target['id']}", json={"amount": 999})
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_patch_cell_negative_amount_returns_400(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01"},
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
async def test_delete_override_clears_and_redistributes(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01"},
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
async def test_grid_empty_no_lines(client: AsyncClient) -> None:
    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026")
    assert resp.status_code == 200
    body = resp.json()
    assert body["lines"] == []
    assert body["cells"] == []
    assert len(body["months"]) == 12
    assert body["months"][0] == {"year": 2026, "month": 1}
    assert body["months"][-1] == {"year": 2026, "month": 12}


@pytest.mark.asyncio
async def test_grid_returns_lines_and_cells(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    p = await client.post(
        "/api/projects",
        json={
            "name": "Grid Test",
            "code": "TEST.AC.GRID1",
            "currency": "USD",
            "budget": 1200,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    pid = UUID(p.json()["id"])
    line = await _make_line(
        db_session,
        excel_code="TEST.AC.GRID1",
        currency="USD",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
        cells=[(2026, m, "100") for m in range(1, 13)],
        project_ids=[pid],
    )

    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["lines"]) == 1
    row = body["lines"][0]
    assert row["id"] == str(line.id)
    assert row["excel_code"] == "TEST.AC.GRID1"
    assert [p["id"] for p in row["projects"]] == [str(pid)]
    assert len(body["cells"]) == 12
    assert all(c["line_id"] == str(line.id) for c in body["cells"])


@pytest.mark.asyncio
async def test_grid_year_range_validation(client: AsyncClient) -> None:
    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2024")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_grid_currency_filters_on_line_currency(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The currency filter matches the line's own (ISO) currency."""
    win = {"window_start": date(2026, 1, 1), "window_end": date(2026, 12, 1)}
    await _make_line(db_session, excel_code="USD1", currency="USD", **win)
    await _make_line(db_session, excel_code="USD2", currency="USD", **win)
    await _make_line(db_session, excel_code="GBP1", currency="GBP", **win)

    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026&currency=USD")
    assert resp.status_code == 200
    codes = {row["excel_code"] for row in resp.json()["lines"]}
    assert codes == {"USD1", "USD2"}


@pytest.mark.asyncio
async def test_grid_filter_by_status(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """status filter keeps lines with a linked project in that status."""
    win = {"window_start": date(2026, 1, 1), "window_end": date(2026, 12, 1)}
    live = await client.post(
        "/api/projects",
        json={
            "name": "Live one",
            "code": "TEST.AC.GRID.LIVE",
            "currency": "USD",
            "status": "live",
            "budget": 1000,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    prop = await client.post(
        "/api/projects",
        json={
            "name": "Proposal",
            "code": "TEST.AC.GRID.PROP",
            "currency": "USD",
            "status": "proposal",
            "budget": 1000,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    await _make_line(db_session, excel_code="L-LIVE", project_ids=[UUID(live.json()["id"])], **win)
    await _make_line(db_session, excel_code="L-PROP", project_ids=[UUID(prop.json()["id"])], **win)

    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026&status=live")
    assert resp.status_code == 200
    codes = {row["excel_code"] for row in resp.json()["lines"]}
    assert codes == {"L-LIVE"}


@pytest.mark.asyncio
async def test_bulk_cells_happy_path(client: AsyncClient) -> None:
    await client.post(
        "/api/accrual/periods",
        json={"start_date": "2026-01-01"},
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


@pytest.mark.asyncio
async def test_grid_returns_bounds_and_currencies(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """bounds span every filtered line's window; available_currencies are the
    line currencies — both independent of the year/currency filters."""
    await _make_line(
        db_session,
        excel_code="TEST.AC.B1",
        currency="USD",
        window_start=date(2022, 1, 1),
        window_end=date(2024, 12, 1),
    )
    await _make_line(
        db_session,
        excel_code="TEST.AC.B2",
        currency="GBP",
        window_start=date(2026, 1, 1),
        window_end=date(2027, 12, 1),
    )

    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026")
    assert resp.status_code == 200
    body = resp.json()
    # Year filter narrows the rendered line list but bounds reflect the wider span.
    assert body["bounds"] == {"min_year": 2022, "max_year": 2027}
    # USD comes from the legacy 'dollar' label, normalised.
    assert body["available_currencies"] == ["GBP", "USD"]


@pytest.mark.asyncio
async def test_grid_bounds_null_when_no_lines(client: AsyncClient) -> None:
    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026")
    assert resp.status_code == 200
    body = resp.json()
    assert body["bounds"] is None
    assert body["available_currencies"] == []


@pytest.mark.asyncio
async def test_grid_filters_lines_by_year_overlap(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A line whose window ended before the visible range is dropped."""
    await _make_line(
        db_session,
        excel_code="TEST.AC.OVL1",
        window_start=date(2022, 1, 1),
        window_end=date(2024, 12, 1),
    )
    await _make_line(
        db_session,
        excel_code="TEST.AC.OVL2",
        window_start=date(2026, 1, 1),
        window_end=date(2027, 12, 1),
    )

    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026")
    codes = {row["excel_code"] for row in resp.json()["lines"]}
    assert codes == {"TEST.AC.OVL2"}


@pytest.mark.asyncio
async def test_grid_excludes_lines_without_window(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A line with a null window can't be placed on the year axis — dropped."""
    await _make_line(db_session, excel_code="NOWIN", window_start=None, window_end=None)
    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026")
    codes = {row["excel_code"] for row in resp.json()["lines"]}
    assert "NOWIN" not in codes


@pytest.mark.asyncio
async def test_grid_filter_by_source(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """source filter keeps only lines of that provenance."""
    win = {"window_start": date(2026, 1, 1), "window_end": date(2026, 12, 1)}
    await _make_line(db_session, excel_code="EX1", source=LineSource.EXCEL, **win)
    await _make_line(db_session, excel_code="TB1", source=LineSource.TEAM_BUDGET, **win)

    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026&source=team_budget")
    codes = {row["excel_code"] for row in resp.json()["lines"]}
    assert codes == {"TB1"}


@pytest.mark.asyncio
async def test_grid_unlinked_line_renders_with_no_projects(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A line with zero linked projects still renders (real income, no project)."""
    await _make_line(
        db_session,
        name="Future grant",
        excel_code="UNLINKED1",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
        cells=[(2026, 1, "500")],
    )
    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2026")
    rows = {row["excel_code"]: row for row in resp.json()["lines"]}
    assert "UNLINKED1" in rows
    assert rows["UNLINKED1"]["projects"] == []
    assert rows["UNLINKED1"]["name"] == "Future grant"


def test_line_health_ok_when_cells_match_value():
    from app.modules.accrual.api.cells import _line_health

    h = _line_health(value_eur=Decimal("100"), sum_cells=Decimal("100"))
    assert h["status"] == "ok"
    assert h["diff_eur"] == "0.00"
    assert h["diff_pct"] == 0.0


def test_line_health_warning_when_diff_above_5pct():
    from app.modules.accrual.api.cells import _line_health

    h = _line_health(value_eur=Decimal("100"), sum_cells=Decimal("108"))
    assert h["status"] == "warning"
    assert h["diff_pct"] == 8.0


def test_line_health_critical_when_diff_above_20pct():
    from app.modules.accrual.api.cells import _line_health

    h = _line_health(value_eur=Decimal("100"), sum_cells=Decimal("125"))
    assert h["status"] == "critical"
    assert h["diff_pct"] == 25.0


def test_line_health_no_data_when_value_zero():
    from app.modules.accrual.api.cells import _line_health

    h = _line_health(value_eur=Decimal("0"), sum_cells=Decimal("0"))
    assert h["status"] == "no_data"
    assert h["diff_pct"] is None


def test_line_health_no_data_when_value_none():
    from app.modules.accrual.api.cells import _line_health

    h = _line_health(value_eur=None, sum_cells=Decimal("0"))
    assert h["status"] == "no_data"


def test_line_health_critical_when_value_but_no_cells():
    from app.modules.accrual.api.cells import _line_health

    h = _line_health(value_eur=Decimal("100"), sum_cells=Decimal("0"))
    assert h["status"] == "critical"
    assert h["diff_pct"] == 100.0
