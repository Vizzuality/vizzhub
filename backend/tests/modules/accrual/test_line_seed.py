"""Smoke test for the one-time line seed (slice 3).

Exercises ``seed_lines_from_excel_rows`` end-to-end: Excel rows become lines with
**verbatim** cells (no gating, no redistribution), explicit link/unlink/exclude
overlays are honoured, eligible projects with no Excel line get a team_budget
line, and closed-period cells are re-frozen.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.models.accrual_excel_row import AccrualExcelRowDB
from app.modules.accrual.models.accrual_import_run import AccrualImportRunDB
from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
from app.modules.accrual.services.line_seed import seed_lines_from_excel_rows


def _row(run_id: UUID, pos: int, code: str, value_eur: str, cells: list[dict]) -> AccrualExcelRowDB:
    return AccrualExcelRowDB(
        import_run_id=run_id,
        import_run_position=pos,
        excel_code=code,
        name=f"Row {code}",
        value_eur=Decimal(value_eur),
        monthly_cells=cells,
    )


@pytest_asyncio.fixture
async def _seed_world(db_session: AsyncSession) -> dict:
    """An import run with 3 excel rows + 2 eligible projects + an open period."""
    run = AccrualImportRunDB(id=uuid4())
    db_session.add(run)

    proj_match = ProjectDB(
        name="Matched",
        code="SMK.MATCH",
        status="live",
        currency="dollar",
        is_billable=True,
        budget=Decimal("1200"),
        start_date=date(2025, 12, 1),
        end_date=date(2026, 1, 1),
    )
    proj_tb = ProjectDB(
        name="TeamBudget",
        code="SMK.TB",
        status="live",
        currency="dollar",
        is_billable=True,
        budget=Decimal("600"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 6, 1),
    )
    db_session.add_all([proj_match, proj_tb])

    # Open period starting 2026-01-01 → any cell before it freezes.
    db_session.add(AccrualPeriodDB(start_date=date(2026, 1, 1), status="open"))
    await db_session.flush()

    db_session.add_all(
        [
            _row(
                run.id,
                0,
                "SMK.MATCH",
                "1200",
                [
                    {"year": 2025, "month": 12, "eur_amount": "600"},
                    {"year": 2026, "month": 1, "eur_amount": "600"},
                ],
            ),
            _row(run.id, 1, "SMK.UNLINK", "500", [{"year": 2026, "month": 3, "eur_amount": "500"}]),
            _row(run.id, 2, "SMK.EXCL", "999", [{"year": 2026, "month": 4, "eur_amount": "999"}]),
        ]
    )
    await db_session.flush()
    return {"run_id": run.id, "proj_match": proj_match.id, "proj_tb": proj_tb.id}


@pytest.mark.asyncio
async def test_seed_builds_lines_links_and_cells(
    db_session: AsyncSession, _seed_world: dict
) -> None:
    report = await seed_lines_from_excel_rows(
        db_session,
        import_run_id=_seed_world["run_id"],
        links_by_id={"SMK.MATCH": [_seed_world["proj_match"]]},
        unlinked_codes={"SMK.UNLINK"},
        excluded_codes={"SMK.EXCL"},
    )

    assert report["lines_excel"] == 1
    assert report["lines_unlinked"] == 1
    assert report["lines_team_budget"] == 1
    assert report["excluded"] == 1
    # 2 matched cells + 1 unlinked cell; 6 team_budget cells.
    assert report["excel_cells"] == 3
    assert report["team_budget_cells"] == 6
    # Matched line links to its project; team_budget line links to its own.
    assert report["links"] == 2


@pytest.mark.asyncio
async def test_seed_excel_line_is_verbatim(db_session: AsyncSession, _seed_world: dict) -> None:
    await seed_lines_from_excel_rows(
        db_session,
        import_run_id=_seed_world["run_id"],
        links_by_id={"SMK.MATCH": [_seed_world["proj_match"]]},
        unlinked_codes={"SMK.UNLINK"},
        excluded_codes={"SMK.EXCL"},
    )
    line = (
        await db_session.execute(
            select(AccrualLineDB).where(AccrualLineDB.excel_code == "SMK.MATCH")
        )
    ).scalar_one()
    cells = (
        (
            await db_session.execute(
                select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.line_id == line.id)
            )
        )
        .scalars()
        .all()
    )
    # Σcells == the Excel monthly_cells total, cell-for-cell (no gating, no redistribution).
    assert sum(c.amount for c in cells) == Decimal("1200")
    assert line.source == LineSource.EXCEL.value
    # Currency derived from the linked legacy 'dollar' project.
    assert line.currency == "USD"


@pytest.mark.asyncio
async def test_seed_excluded_code_produces_no_line(
    db_session: AsyncSession, _seed_world: dict
) -> None:
    await seed_lines_from_excel_rows(
        db_session,
        import_run_id=_seed_world["run_id"],
        links_by_id={"SMK.MATCH": [_seed_world["proj_match"]]},
        unlinked_codes={"SMK.UNLINK"},
        excluded_codes={"SMK.EXCL"},
    )
    excl = (
        await db_session.execute(
            select(AccrualLineDB).where(AccrualLineDB.excel_code == "SMK.EXCL")
        )
    ).scalar_one_or_none()
    assert excl is None


@pytest.mark.asyncio
async def test_seed_unlinked_line_has_no_projects(
    db_session: AsyncSession, _seed_world: dict
) -> None:
    await seed_lines_from_excel_rows(
        db_session,
        import_run_id=_seed_world["run_id"],
        links_by_id={"SMK.MATCH": [_seed_world["proj_match"]]},
        unlinked_codes={"SMK.UNLINK"},
        excluded_codes={"SMK.EXCL"},
    )
    line = (
        await db_session.execute(
            select(AccrualLineDB).where(AccrualLineDB.excel_code == "SMK.UNLINK")
        )
    ).scalar_one()
    links = (
        (
            await db_session.execute(
                select(AccrualLineProjectDB).where(AccrualLineProjectDB.line_id == line.id)
            )
        )
        .scalars()
        .all()
    )
    assert links == []


@pytest.mark.asyncio
async def test_seed_refreezes_closed_period_cells(
    db_session: AsyncSession, _seed_world: dict
) -> None:
    await seed_lines_from_excel_rows(
        db_session,
        import_run_id=_seed_world["run_id"],
        links_by_id={"SMK.MATCH": [_seed_world["proj_match"]]},
        unlinked_codes={"SMK.UNLINK"},
        excluded_codes={"SMK.EXCL"},
    )
    line = (
        await db_session.execute(
            select(AccrualLineDB).where(AccrualLineDB.excel_code == "SMK.MATCH")
        )
    ).scalar_one()
    by_month = {
        (c.year, c.month): c
        for c in (
            await db_session.execute(
                select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.line_id == line.id)
            )
        )
        .scalars()
        .all()
    }
    # Open period starts 2026-01-01 → Dec-2025 frozen, Jan-2026 still mutable.
    assert by_month[(2025, 12)].is_frozen is True
    assert by_month[(2025, 12)].frozen_eur_amount == Decimal("600")
    assert by_month[(2026, 1)].is_frozen is False


@pytest.mark.asyncio
async def test_seed_team_budget_line_for_unmatched_project(
    db_session: AsyncSession, _seed_world: dict
) -> None:
    await seed_lines_from_excel_rows(
        db_session,
        import_run_id=_seed_world["run_id"],
        links_by_id={"SMK.MATCH": [_seed_world["proj_match"]]},
        unlinked_codes={"SMK.UNLINK"},
        excluded_codes={"SMK.EXCL"},
    )
    tb_line = (
        await db_session.execute(
            select(AccrualLineDB).where(AccrualLineDB.source == LineSource.TEAM_BUDGET.value)
        )
    ).scalar_one()
    assert tb_line.excel_code == "SMK.TB"
    assert tb_line.value_eur == Decimal("600")
    cells = (
        (
            await db_session.execute(
                select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.line_id == tb_line.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(cells) == 6
    assert sum(c.amount for c in cells) == Decimal("600")
