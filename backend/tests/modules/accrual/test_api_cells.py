"""HTTP tests for /api/accrual/cells, /api/accrual/lines/{id}/cells and the grid."""

from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
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

_DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def _make_line(
    db: AsyncSession,
    *,
    value_eur: str = "1200",
    source: LineSource = LineSource.EXCEL,
    excel_code: str | None = None,
    name: str = "Line",
    currency: str | None = None,
    value_orig: str | None = None,
    rate: str | None = None,
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
        value_orig=Decimal(value_orig) if value_orig is not None else None,
        rate=Decimal(rate) if rate is not None else None,
        window_start=window_start,
        window_end=window_end,
    )
    db.add(line)
    await db.flush()
    for pid in project_ids or []:
        db.add(AccrualLineProjectDB(line_id=line.id, project_id=pid))
    for year, month, amount in cells or []:
        db.add(
            AccrualCellDB(
                line_id=line.id,
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
async def test_patch_cell_sets_override(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    line = await _make_line(
        db_session,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
        cells=[(2026, m, "100") for m in range(1, 13)],
    )
    cells = (await client.get("/api/accrual/grid?year_from=2026&year_to=2026")).json()["cells"]
    target = next(c for c in cells if c["line_id"] == str(line.id) and c["month"] == 5)

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
    line = await _make_line(
        db_session,
        window_start=date(2025, 1, 1),
        window_end=date(2025, 12, 1),
        cells=[(2025, 3, "100")],
    )
    res = await db_session.execute(select(AccrualCellDB).where(AccrualCellDB.line_id == line.id))
    cell = res.scalar_one()
    cell.is_frozen = True
    cell.frozen_at = datetime.now(UTC)
    cell.frozen_eur_amount = cell.amount
    await db_session.commit()

    resp = await client.patch(f"/api/accrual/cells/{cell.id}", json={"amount": 999})
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_patch_cell_negative_amount_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    line = await _make_line(
        db_session,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
        cells=[(2026, 1, "100")],
    )
    res = await db_session.execute(select(AccrualCellDB).where(AccrualCellDB.line_id == line.id))
    cell = res.scalar_one()

    resp = await client.patch(f"/api/accrual/cells/{cell.id}", json={"amount": -10})
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_delete_override_clears_and_redistributes(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await client.post("/api/accrual/periods", json={"start_date": "2026-01-01"})
    line = await _make_line(
        db_session,
        value_eur="1200",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
        cells=[(2026, m, "100") for m in range(1, 13)],
    )
    cells = (await client.get("/api/accrual/grid?year_from=2026&year_to=2026")).json()["cells"]
    target = next(c for c in cells if c["line_id"] == str(line.id) and c["month"] == 5)
    await client.patch(f"/api/accrual/cells/{target['id']}", json={"amount": 300})

    resp = await client.delete(f"/api/accrual/cells/{target['id']}/override")
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_manual_override"] is False
    assert Decimal(resp.json()["amount"]) == Decimal("100.00")


@pytest.mark.asyncio
async def test_upsert_line_cell_creates_on_empty_month(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Editing a previously-empty month creates the cell as a manual override."""
    line = await _make_line(
        db_session,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
        cells=[(2026, 1, "100")],
    )
    resp = await client.put(
        f"/api/accrual/lines/{line.id}/cells",
        json={"year": 2026, "month": 7, "amount": 500},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["line_id"] == str(line.id)
    assert body["year"] == 2026
    assert body["month"] == 7
    assert Decimal(body["amount"]) == Decimal("500.00")
    assert body["is_manual_override"] is True


@pytest.mark.asyncio
async def test_upsert_line_cell_updates_existing(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    line = await _make_line(
        db_session,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
        cells=[(2026, 3, "100")],
    )
    resp = await client.put(
        f"/api/accrual/lines/{line.id}/cells",
        json={"year": 2026, "month": 3, "amount": 650},
    )
    assert resp.status_code == 200, resp.text
    assert Decimal(resp.json()["amount"]) == Decimal("650.00")
    assert resp.json()["is_manual_override"] is True


@pytest.mark.asyncio
async def test_upsert_line_cell_line_not_found(client: AsyncClient) -> None:
    resp = await client.put(
        "/api/accrual/lines/00000000-0000-0000-0000-0000000000ff/cells",
        json={"year": 2026, "month": 1, "amount": 100},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_upsert_line_cell_frozen_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    line = await _make_line(
        db_session,
        window_start=date(2025, 1, 1),
        window_end=date(2025, 12, 1),
        cells=[(2025, 3, "100")],
    )
    res = await db_session.execute(select(AccrualCellDB).where(AccrualCellDB.line_id == line.id))
    cell = res.scalar_one()
    cell.is_frozen = True
    cell.frozen_at = datetime.now(UTC)
    cell.frozen_eur_amount = cell.amount
    await db_session.commit()

    resp = await client.put(
        f"/api/accrual/lines/{line.id}/cells",
        json={"year": 2025, "month": 3, "amount": 999},
    )
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_redistribute_line_spreads_value(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST redistribute spreads value_eur uniformly across the window's months."""
    await client.post("/api/accrual/periods", json={"start_date": "2026-01-01"})
    line = await _make_line(
        db_session,
        value_eur="1200",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
    )
    resp = await client.post(f"/api/accrual/lines/{line.id}/redistribute", json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["cells_updated"] == 12

    cells = (await client.get("/api/accrual/grid?year_from=2026&year_to=2026")).json()["cells"]
    line_cells = [c for c in cells if c["line_id"] == str(line.id)]
    assert len(line_cells) == 12
    assert all(Decimal(c["amount"]) == Decimal("100.00") for c in line_cells)


@pytest.mark.asyncio
async def test_redistribute_line_not_found(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/accrual/lines/00000000-0000-0000-0000-0000000000ff/redistribute",
        json={},
    )
    assert resp.status_code == 404, resp.text


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
async def test_grid_exposes_line_rate_without_touching_cells(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The per-line rate is surfaced for display; cell amounts are returned verbatim
    (the rate never converts/transforms the stored EUR cells)."""
    line = await _make_line(
        db_session,
        excel_code="RATE.USD",
        currency="USD",
        value_orig="108",
        rate="1.08",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
        cells=[(2026, 1, "100.00"), (2026, 2, "250.00")],
    )
    body = (await client.get("/api/accrual/grid?year_from=2026&year_to=2026")).json()
    row = next(r for r in body["lines"] if r["id"] == str(line.id))
    assert row["rate"] == "1.08"
    # Cells unchanged by the rate: stored 100/250 EUR come back as-is.
    amounts = sorted(c["eur_amount"] for c in body["cells"] if c["line_id"] == str(line.id))
    assert amounts == ["100.00", "250.00"]


@pytest.mark.asyncio
async def test_grid_data_quality_note_on_foreign_line_without_original(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A non-EUR Excel line missing its original amount is flagged; others are not."""
    win = {"window_start": date(2026, 1, 1), "window_end": date(2026, 12, 1)}
    flagged = await _make_line(
        db_session,
        excel_code="DQ.GBP",
        currency="GBP",
        value_orig=None,
        cells=[(2026, 1, "100")],
        **win,
    )
    eur_line = await _make_line(
        db_session,
        excel_code="DQ.EUR",
        currency="EUR",
        cells=[(2026, 1, "100")],
        **win,
    )
    usd_ok = await _make_line(
        db_session,
        excel_code="DQ.USD",
        currency="USD",
        value_orig="108",
        cells=[(2026, 1, "100")],
        **win,
    )

    rows = {
        r["id"]: r
        for r in (await client.get("/api/accrual/grid?year_from=2026&year_to=2026")).json()["lines"]
    }
    assert rows[str(flagged.id)]["data_quality_note"] is not None
    assert rows[str(eur_line.id)]["data_quality_note"] is None
    assert rows[str(usd_ok.id)]["data_quality_note"] is None


@pytest.mark.asyncio
async def test_grid_year_range_validation(client: AsyncClient) -> None:
    resp = await client.get("/api/accrual/grid?year_from=2026&year_to=2024")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_grid_rejects_oversized_year_span(client: AsyncClient) -> None:
    """A huge user-supplied span is rejected (caps the range() — no giant list / DoS)."""
    resp = await client.get("/api/accrual/grid?year_from=0&year_to=999999")
    assert resp.status_code == 400, resp.text
    assert "span" in resp.json()["detail"].lower()


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
async def test_bulk_cells_happy_path(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    line = await _make_line(
        db_session,
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
    )

    resp = await client.post(
        "/api/accrual/cells/bulk",
        json={
            "updates": [
                {"line_id": str(line.id), "year": 2026, "month": 2, "amount": 150},
                {"line_id": str(line.id), "year": 2026, "month": 3, "amount": 200},
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


@pytest.mark.asyncio
async def test_grid_flags_dates_diverged(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A single-project line whose window differs from the project's contract
    dates is flagged; a matching single-project line and a multi-project line
    are not."""
    diverged_proj = await client.post(
        "/api/projects",
        json={
            "name": "Diverged",
            "code": "TEST.AC.DIV",
            "currency": "euro",
            "budget": 100,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    matching_proj = await client.post(
        "/api/projects",
        json={
            "name": "Matching",
            "code": "TEST.AC.MATCH",
            "currency": "euro",
            "budget": 100,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    sibling_a = await client.post(
        "/api/projects",
        json={
            "name": "Sibling A",
            "code": "TEST.AC.SIBA",
            "currency": "euro",
            "budget": 100,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    sibling_b = await client.post(
        "/api/projects",
        json={
            "name": "Sibling B",
            "code": "TEST.AC.SIBB",
            "currency": "euro",
            "budget": 100,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )

    diverged = await _make_line(
        db_session,
        name="Diverged",
        source=LineSource.TEAM_BUDGET,
        value_eur="100",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 6, 1),  # differs from project end (2026-12-01)
        project_ids=[UUID(diverged_proj.json()["id"])],
    )
    matching = await _make_line(
        db_session,
        name="Matching",
        source=LineSource.TEAM_BUDGET,
        value_eur="100",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),  # equals project dates
        project_ids=[UUID(matching_proj.json()["id"])],
    )
    multi = await _make_line(
        db_session,
        name="Multi",
        source=LineSource.TEAM_BUDGET,
        value_eur="100",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 6, 1),
        project_ids=[UUID(sibling_a.json()["id"]), UUID(sibling_b.json()["id"])],
    )

    rows = {
        r["id"]: r
        for r in (await client.get("/api/accrual/grid?year_from=2026&year_to=2026")).json()["lines"]
    }
    assert rows[str(diverged.id)]["dates_diverged"] is True
    assert rows[str(matching.id)]["dates_diverged"] is False
    assert rows[str(multi.id)]["dates_diverged"] is False


@pytest.mark.asyncio
async def test_grid_excel_line_never_flagged_dates_diverged(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """An Excel line sets its window from the Excel month span (union with contract
    dates), so a single-project Excel line whose window differs from the project's
    contract dates is by design — never an R6 divergence."""
    excel_proj = await client.post(
        "/api/projects",
        json={
            "name": "Excel Divergent",
            "code": "TEST.AC.XLS",
            "currency": "euro",
            "budget": 100,
            "start_date": "2026-01-01",
            "end_date": "2026-12-01",
        },
    )
    excel = await _make_line(
        db_session,
        name="Excel Divergent",
        source=LineSource.EXCEL,
        value_eur="100",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 6, 1),  # differs from project end (2026-12-01) by design
        project_ids=[UUID(excel_proj.json()["id"])],
    )

    rows = {
        r["id"]: r
        for r in (await client.get("/api/accrual/grid?year_from=2026&year_to=2026")).json()["lines"]
    }
    assert rows[str(excel.id)]["dates_diverged"] is False


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


@pytest.mark.asyncio
async def test_grid_line_includes_period_rate(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A USD line whose window falls in a period with fx_rates["USD"] = "1.10"
    surfaces that rate as period_rate; EUR lines and lines without a rate get None."""
    from app.modules.accrual.models.accrual_period import AccrualPeriodDB

    period = AccrualPeriodDB(
        start_date=date(2026, 1, 1),
        status="open",
        created_by=_DEV_USER_ID,
        fx_rates={"USD": "1.10"},
    )
    db_session.add(period)
    await db_session.flush()

    usd_line = await _make_line(
        db_session,
        excel_code="PR.USD",
        currency="USD",
        value_orig="110",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 31),
        cells=[(2026, 1, "100")],
    )
    eur_line = await _make_line(
        db_session,
        excel_code="PR.EUR",
        currency="EUR",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 31),
        cells=[(2026, 1, "100")],
    )

    resp = await client.get("/api/accrual/grid", params={"year_from": 2026, "year_to": 2026})
    assert resp.status_code == 200
    rows = {r["excel_code"]: r for r in resp.json()["lines"]}

    assert rows["PR.USD"]["period_rate"] == "1.10"
    assert "rate" in rows["PR.USD"]
    assert rows["PR.EUR"]["period_rate"] is None


@pytest_asyncio.fixture
async def manager_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """accrual:manage but NOT accrual:period_manage — cannot edit frozen cells."""

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
async def test_redistribute_include_frozen_requires_period_manage(
    manager_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    line = await _make_line(
        db_session,
        value_eur="1200",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
    )
    resp = await manager_client.post(
        f"/api/accrual/lines/{line.id}/redistribute", json={"include_frozen": True}
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_redistribute_include_frozen_admin_rewrites_frozen(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    line = await _make_line(
        db_session,
        value_eur="2400",
        window_start=date(2026, 1, 1),
        window_end=date(2026, 12, 1),
        cells=[(2026, m, "100") for m in range(1, 13)],
    )
    res = await db_session.execute(
        select(AccrualCellDB).where(AccrualCellDB.line_id == line.id, AccrualCellDB.month == 1)
    )
    frozen = res.scalar_one()
    frozen.is_frozen = True
    frozen.frozen_at = datetime.now(UTC)
    frozen.frozen_eur_amount = frozen.amount
    await db_session.commit()

    resp = await client.post(
        f"/api/accrual/lines/{line.id}/redistribute", json={"include_frozen": True}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["cells_updated"] == 12

    cells = (await client.get("/api/accrual/grid?year_from=2026&year_to=2026")).json()["cells"]
    jan = next(c for c in cells if c["line_id"] == str(line.id) and c["month"] == 1)
    assert jan["is_frozen"] is True
    assert Decimal(jan["amount"]) == Decimal("200.00")  # 2400 / 12
    assert Decimal(jan["frozen_eur_amount"]) == Decimal("200.00")  # synced
