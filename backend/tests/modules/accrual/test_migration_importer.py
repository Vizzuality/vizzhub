"""Migration script integration tests."""

import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "accrual_minimal.xlsx"


def test_script_help_runs():
    proc = subprocess.run(
        [sys.executable, "scripts/import_accrual_spreadsheet.py", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[3],
    )
    assert proc.returncode == 0
    assert "--spreadsheet" in proc.stdout
    assert "--dry-run" in proc.stdout
    assert "--periods-only" in proc.stdout


def test_normalize_code_strips_internal_whitespace_and_collapses_dots():
    from scripts.import_accrual_spreadsheet import _normalize_code

    assert _normalize_code("LSE .TPI2025 .35054413") == "LSE.TPI2025.35054413"
    assert _normalize_code("ICIMOD..34229341") == "ICIMOD.34229341"
    assert _normalize_code("  hal.halfe4  ") == "HAL.HALFE4"
    assert _normalize_code(None) is None
    assert _normalize_code("   ") is None


def test_code_prefix_strips_trailing_segment():
    from scripts.import_accrual_spreadsheet import _code_prefix

    assert _code_prefix("TNC.BCCT.32232147") == "TNC.BCCT"
    assert _code_prefix("AFOC.AMVP.24") == "AFOC.AMVP"
    assert _code_prefix("HAL.HALFE4.24/25") == "HAL.HALFE4"
    # No-op when stripping wouldn't shorten or leaves nothing.
    assert _code_prefix("AFOC") is None
    assert _code_prefix(None) is None


@pytest.mark.asyncio
async def test_match_via_excel_suffix(db_session, _ensure_fixture):
    """DB project has the bare code; Excel row has trailing Jira ID. Matches via Excel prefix."""
    from datetime import date
    from decimal import Decimal

    from app.core.models.project import ProjectDB
    from scripts.import_accrual_spreadsheet import (
        SpreadsheetRow,
        bootstrap_periods,
        import_projects,
        parse_spreadsheet,
    )

    db_session.add(
        ProjectDB(
            name="bare",
            code="TNC.BCCT",
            status="finished",
            currency="USD",
            is_billable=True,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 1),
        )
    )
    await db_session.flush()

    base_rows = parse_spreadsheet(FIXTURE)
    extra_row = SpreadsheetRow(
        type="2-Signed",
        code="TNC.BCCT.32232147",
        pm=None,
        name="TNC Blue Carbon Cost tool",
        value=Decimal("50000"),
        rate=Decimal("1.1"),
        value_eur=Decimal("45454.54"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 1),
        duration=12,
        monthly={(2024, m): Decimal("4166.67") for m in range(1, 13)},
    )
    rows = [*base_rows, extra_row]

    await bootstrap_periods(db_session, rows, current_year=2026)
    report = await import_projects(db_session, rows)

    assert report["matched"] >= 1
    assert not any(u["code"] == "TNC.BCCT.32232147" for u in report["unmatched"])


@pytest.mark.asyncio
async def test_match_via_db_suffix(db_session, _ensure_fixture):
    """DB project has trailing suffix; Excel row has the bare prefix. Matches via DB prefix."""
    from datetime import date
    from decimal import Decimal

    from app.core.models.project import ProjectDB
    from scripts.import_accrual_spreadsheet import (
        SpreadsheetRow,
        bootstrap_periods,
        import_projects,
        parse_spreadsheet,
    )

    db_session.add(
        ProjectDB(
            name="suffix",
            code="HAL.HALFE4.24/25",
            status="finished",
            currency="USD",
            is_billable=True,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 1),
        )
    )
    await db_session.flush()

    base_rows = parse_spreadsheet(FIXTURE)
    extra_row = SpreadsheetRow(
        type="2-Signed",
        code="HAL.HALFE4",
        pm=None,
        name="Half-Earth 2024/2026",
        value=Decimal("100000"),
        rate=Decimal("1.08"),
        value_eur=Decimal("92592.59"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 1),
        duration=12,
        monthly={(2024, m): Decimal("8333.33") for m in range(1, 13)},
    )
    rows = [*base_rows, extra_row]

    await bootstrap_periods(db_session, rows, current_year=2026)
    report = await import_projects(db_session, rows)

    assert report["matched"] >= 1
    assert not any(u["code"] == "HAL.HALFE4" for u in report["unmatched"])


def test_consolidate_duplicates_sums_value_and_merges_monthly():
    from datetime import date
    from decimal import Decimal

    from scripts.import_accrual_spreadsheet import (
        SpreadsheetRow,
        consolidate_duplicate_rows,
    )

    rows = [
        SpreadsheetRow(
            type="2-Signed",
            code="X",
            pm=None,
            name="X",
            value=Decimal("100"),
            rate=Decimal("1.0"),
            value_eur=Decimal("100"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 1),
            duration=6,
            monthly={(2024, m): Decimal("16.67") for m in range(1, 7)},
        ),
        SpreadsheetRow(
            type="2-Signed",
            code="X",
            pm=None,
            name="X amendment",
            value=Decimal("50"),
            rate=Decimal("1.1"),
            value_eur=Decimal("45.45"),
            start_date=date(2024, 7, 1),
            end_date=date(2024, 12, 1),
            duration=6,
            monthly={(2024, m): Decimal("8.33") for m in range(7, 13)},
        ),
        SpreadsheetRow(
            type="2-Signed",
            code="Y",
            pm=None,
            name="Y solo",
            value=Decimal("999"),
            rate=Decimal("1.0"),
            value_eur=Decimal("999"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 1),
            duration=12,
            monthly={(2024, 1): Decimal("999")},
        ),
    ]
    out = consolidate_duplicate_rows(rows)
    assert len(out) == 2  # X merged, Y untouched

    x_row = next(r for r in out if r.code == "X")
    assert x_row.value == Decimal("150")
    assert x_row.start_date == date(2024, 1, 1)
    assert x_row.end_date == date(2024, 12, 1)
    assert len(x_row.monthly) == 12
    assert x_row.monthly[(2024, 1)] == Decimal("16.67")
    assert x_row.monthly[(2024, 12)] == Decimal("8.33")
    assert "amendment" in (x_row.name or "")


def test_consolidate_sums_monthly_when_groups_overlap():
    from datetime import date
    from decimal import Decimal

    from scripts.import_accrual_spreadsheet import (
        SpreadsheetRow,
        consolidate_duplicate_rows,
    )

    rows = [
        SpreadsheetRow(
            type="2-Signed",
            code="X",
            pm=None,
            name="X",
            value=Decimal("100"),
            rate=Decimal("1.0"),
            value_eur=Decimal("100"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 1),
            duration=12,
            monthly={(2024, 6): Decimal("50")},
        ),
        SpreadsheetRow(
            type="2-Signed",
            code="X",
            pm=None,
            name="X amend",
            value=Decimal("30"),
            rate=Decimal("1.0"),
            value_eur=Decimal("30"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 1),
            duration=12,
            monthly={(2024, 6): Decimal("20")},  # same month, different amount
        ),
    ]
    out = consolidate_duplicate_rows(rows)
    assert len(out) == 1
    assert out[0].value == Decimal("130")
    assert out[0].monthly[(2024, 6)] == Decimal("70")  # 50 + 20 summed


@pytest.mark.asyncio
async def test_import_reports_date_mismatches_without_mutating_project(db_session, _ensure_fixture):
    """Excel rows outside the DB project's date range produce a date_mismatch
    entry with orphan-cell counts; the project record is NOT mutated."""
    from datetime import date
    from decimal import Decimal

    from app.core.models.project import ProjectDB
    from scripts.import_accrual_spreadsheet import (
        SpreadsheetRow,
        bootstrap_periods,
        consolidate_duplicate_rows,
        import_projects,
        parse_spreadsheet,
    )

    db_session.add(
        ProjectDB(
            name="multi-year",
            code="EXT.AMD",
            status="live",
            currency="USD",
            is_billable=True,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 1),
        )
    )
    await db_session.flush()

    base_rows = parse_spreadsheet(FIXTURE)
    amend_row_1 = SpreadsheetRow(
        type="2-Signed",
        code="EXT.AMD",
        pm=None,
        name="base",
        value=Decimal("12000"),
        rate=Decimal("1.1"),
        value_eur=Decimal("10909.09"),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 1),
        duration=12,
        monthly={(2024, m): Decimal("1000") for m in range(1, 13)},
    )
    amend_row_2 = SpreadsheetRow(
        type="2-Signed",
        code="EXT.AMD",
        pm=None,
        name="extension",
        value=Decimal("12000"),
        rate=Decimal("1.1"),
        value_eur=Decimal("10909.09"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 1),
        duration=12,
        monthly={(2026, m): Decimal("1000") for m in range(1, 13)},
    )
    rows = [*base_rows, amend_row_1, amend_row_2]
    consolidated = consolidate_duplicate_rows(rows)

    await bootstrap_periods(db_session, rows, current_year=2026)
    report = await import_projects(db_session, consolidated)

    from sqlalchemy import select

    project = (
        await db_session.execute(select(ProjectDB).where(ProjectDB.code == "EXT.AMD"))
    ).scalar_one()
    # DB dates UNCHANGED — importer must not widen the range.
    assert project.start_date == date(2025, 1, 1)
    assert project.end_date == date(2025, 12, 1)
    # original_budget = sum of both amendments (12k + 12k).
    assert project.original_budget == Decimal("24000")
    # Mismatch reported with orphan count: 24 cells (2024 ×12 + 2026 ×12) outside DB range.
    mismatches = [m for m in report["date_mismatches"] if m["code"] == "EXT.AMD"]
    assert len(mismatches) == 1
    assert mismatches[0]["excel_start"] == "2024-01-01"
    assert mismatches[0]["excel_end"] == "2026-12-01"
    assert mismatches[0]["cells_orphaned"] == 24
    assert "dates_extended" not in report


def test_parse_spreadsheet_returns_rows(_ensure_fixture):
    from scripts.import_accrual_spreadsheet import parse_spreadsheet

    rows = parse_spreadsheet(FIXTURE)
    assert len(rows) >= 3
    r = rows[0]
    assert r.code is not None
    assert r.rate > 0
    assert r.start_date is not None
    assert len(r.monthly) >= 12


def test_parse_spreadsheet_captures_override(_ensure_fixture):
    from scripts.import_accrual_spreadsheet import parse_spreadsheet

    rows = parse_spreadsheet(FIXTURE)
    # Contract B has 2024-06 = 2000 (override) vs 1000 baseline.
    b = next(r for r in rows if r.code == "B001")
    assert b.monthly[(2024, 6)] == Decimal("2000.00")


def test_parse_spreadsheet_skips_rows_without_rate(_ensure_fixture):
    from scripts.import_accrual_spreadsheet import parse_spreadsheet

    rows = parse_spreadsheet(FIXTURE)
    codes = {r.code for r in rows}
    assert "A001" in codes
    assert "B001" in codes
    assert "C001" in codes


@pytest.mark.asyncio
async def test_bootstrap_periods_per_year_with_currency_from_projects(
    db_session,
    _ensure_fixture,
):
    from datetime import date

    from app.core.models.project import ProjectDB
    from scripts.import_accrual_spreadsheet import bootstrap_periods, parse_spreadsheet

    # Seed projects matching fixture codes. `currency` is the source of truth.
    db_session.add_all(
        [
            ProjectDB(
                name="A",
                code="A001",
                status="finished",
                currency="EUR",
                is_billable=True,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 1),
            ),
            ProjectDB(
                name="B",
                code="B001",
                status="live",
                currency="USD",
                is_billable=True,
                start_date=date(2024, 1, 1),
                end_date=date(2025, 12, 1),
            ),
            ProjectDB(
                name="C",
                code="C001",
                status="finished",
                currency="USD",
                is_billable=True,
                start_date=date(2025, 1, 1),
                end_date=date(2025, 6, 1),
            ),
        ]
    )
    await db_session.flush()

    rows = parse_spreadsheet(FIXTURE)
    created = await bootstrap_periods(db_session, rows, current_year=2026)

    starts = [p.start_date for p in created]
    assert date(2024, 1, 1) in starts
    assert date(2025, 1, 1) in starts
    assert date(2026, 1, 1) in starts
    open_periods = [p for p in created if p.status == "open"]
    assert len(open_periods) == 1, "exactly one open period at any time"

    p_2024 = next(p for p in created if p.start_date == date(2024, 1, 1))
    # Periods are now empty lifecycle markers — no fx_rates attribute.
    assert not hasattr(p_2024, "fx_rates")


@pytest.mark.asyncio
async def test_bootstrap_periods_no_billable_projects_returns_empty(
    db_session,
    _ensure_fixture,
):
    from scripts.import_accrual_spreadsheet import bootstrap_periods, parse_spreadsheet

    rows = parse_spreadsheet(FIXTURE)
    created = await bootstrap_periods(db_session, rows)
    # No projects seeded in this test → nothing to bootstrap.
    assert created == []


@pytest.mark.asyncio
async def test_import_projects_sets_original_budget_and_historical_freeze(
    db_session,
    _ensure_fixture,
):
    from datetime import date

    from sqlalchemy import select

    from app.core.models.project import ProjectDB
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from scripts.import_accrual_spreadsheet import (
        bootstrap_periods,
        freeze_historical_periods,
        import_projects,
        parse_spreadsheet,
    )

    rows = parse_spreadsheet(FIXTURE)
    # Seed project matching B001 (the fixture row with a 2024-06 override).
    p = ProjectDB(
        name="B",
        code="B001",
        currency="USD",
        is_billable=True,
        budget=Decimal("21818.18"),
        original_budget=None,
        status="live",
        start_date=date(2024, 1, 1),
        end_date=date(2025, 12, 1),
    )
    db_session.add(p)
    await db_session.flush()

    await bootstrap_periods(db_session, rows, current_year=2026)
    report = await import_projects(db_session, rows)
    frozen = await freeze_historical_periods(db_session)

    await db_session.refresh(p)
    # original_budget set from row.value (B001 value is 24000 in fixture).
    assert p.original_budget == Decimal("24000")
    # budget (EUR) set from row.value_eur (B001 value_eur is 21818.18).
    assert p.budget == Decimal("21818.18")

    res = await db_session.execute(
        select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == p.id)
    )
    cells = res.scalars().all()
    assert any(c.is_manual_override for c in cells), "2024-06 must be flagged override"
    cells_2024 = [c for c in cells if c.year == 2024]
    cells_2025 = [c for c in cells if c.year == 2025]
    assert cells_2024 and all(c.is_frozen for c in cells_2024), (
        "2024 cells frozen by historical freeze"
    )
    assert cells_2025 and all(c.is_frozen for c in cells_2025), (
        "2025 cells frozen by historical freeze"
    )
    assert report["matched"] == 1
    assert report["original_budget_set"] == 1
    assert "locked_fx_set" not in report  # field removed from the report
    assert frozen >= 24  # 24 cells frozen across 2024+2025


@pytest.mark.asyncio
async def test_importer_is_idempotent_on_rerun(db_session, _ensure_fixture):
    from datetime import date
    from decimal import Decimal

    from sqlalchemy import select

    from app.core.models.project import ProjectDB
    from app.modules.accrual.models.accrual_period import AccrualPeriodDB
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from scripts.import_accrual_spreadsheet import (
        bootstrap_periods,
        freeze_historical_periods,
        import_projects,
        parse_spreadsheet,
    )

    rows = parse_spreadsheet(FIXTURE)
    p = ProjectDB(
        name="B",
        code="B001",
        currency="USD",
        is_billable=True,
        budget=Decimal("21818.18"),
        original_budget=None,
        status="live",
        start_date=date(2024, 1, 1),
        end_date=date(2025, 12, 1),
    )
    db_session.add(p)
    await db_session.flush()

    # First run — fresh state.
    await bootstrap_periods(db_session, rows, current_year=2026)
    first_report = await import_projects(db_session, rows)
    await freeze_historical_periods(db_session)

    periods_after_first = (await db_session.execute(select(AccrualPeriodDB))).scalars().all()
    cells_after_first = (
        (
            await db_session.execute(
                select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == p.id)
            )
        )
        .scalars()
        .all()
    )
    n_periods_1 = len(periods_after_first)
    n_cells_1 = len(cells_after_first)
    assert first_report["matched"] == 1
    assert first_report["original_budget_set"] == 1
    assert first_report["overrides_imported"] >= 1

    # Second run — must not crash, must not duplicate, must report zero deltas.
    await bootstrap_periods(db_session, rows, current_year=2026)
    second_report = await import_projects(db_session, rows)
    frozen_again = await freeze_historical_periods(db_session)

    periods_after_second = (await db_session.execute(select(AccrualPeriodDB))).scalars().all()
    cells_after_second = (
        (
            await db_session.execute(
                select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == p.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(periods_after_second) == n_periods_1, "no duplicate periods"
    assert len(cells_after_second) == n_cells_1, "no duplicate cells"
    assert second_report["matched"] == 1
    assert second_report["original_budget_set"] == 0, "already set on first run"
    assert second_report["overrides_imported"] == 0, "cell amounts already match"
    assert frozen_again == 0, "all historical cells frozen on first run"


# ──────────────────── Multi-project overlap matching ────────────────────


def _multi_project_row(code: str, monthly_amounts: dict[tuple[int, int], str]):
    """Build a SpreadsheetRow whose monthly cells use ``monthly_amounts``."""
    from datetime import date

    from scripts.import_accrual_spreadsheet import SpreadsheetRow

    monthly = {k: Decimal(v) for k, v in monthly_amounts.items()}
    total_eur = sum(monthly.values(), Decimal("0"))
    return SpreadsheetRow(
        type="2-Signed",
        code=code,
        pm=None,
        name="multi",
        value=total_eur * Decimal("1.08"),  # contractual in USD-ish
        rate=Decimal("1.08"),
        value_eur=total_eur,
        start_date=min(date(y, m, 1) for (y, m) in monthly.keys()),
        end_date=max(date(y, m, 28) for (y, m) in monthly.keys()),
        duration=len(monthly),
        monthly=monthly,
    )


@pytest.mark.asyncio
async def test_multi_project_overlap_imputes_by_date_range(db_session, _ensure_fixture):
    """When one Excel row matches N DB projects (sequential phases of the same
    contract), each monthly cell goes to the project whose date range contains it."""
    from datetime import date

    from sqlalchemy import select

    from app.core.models.project import ProjectDB
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from scripts.import_accrual_spreadsheet import import_projects

    # Two phases of the same contract sharing code "ACME.X". Excel covers
    # 2025-01..2025-06, with 1000 EUR per month.
    db_session.add(
        ProjectDB(
            name="ACME X phase 1",
            code="ACME.X",
            status="finished",
            currency="euro",
            is_billable=True,
            budget=Decimal("3000"),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
        )
    )
    db_session.add(
        ProjectDB(
            name="ACME X phase 2",
            code="ACME.X",
            status="live",
            currency="euro",
            is_billable=True,
            budget=Decimal("3000"),
            start_date=date(2025, 4, 1),
            end_date=date(2025, 6, 30),
        )
    )
    await db_session.flush()

    row = _multi_project_row(
        "ACME.X",
        {(2025, m): "1000" for m in range(1, 7)},
    )
    report = await import_projects(db_session, [row])

    # report records a multi_project_group entry
    assert len(report["multi_project_groups"]) == 1
    group = report["multi_project_groups"][0]
    assert group["code"] == "ACME.X"
    assert group["orphan_cells"] == 0
    assert group["ambiguous_cells"] == 0
    assert len(group["projects"]) == 2

    # Phase 1 gets cells for Jan-Mar; phase 2 for Apr-Jun.
    ps = (
        (await db_session.execute(select(ProjectDB).where(ProjectDB.code == "ACME.X")))
        .scalars()
        .all()
    )
    by_start = {p.start_date: p for p in ps}
    p1 = by_start[date(2025, 1, 1)]
    p2 = by_start[date(2025, 4, 1)]

    cells_1 = (
        (
            await db_session.execute(
                select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == p1.id)
            )
        )
        .scalars()
        .all()
    )
    cells_2 = (
        (
            await db_session.execute(
                select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == p2.id)
            )
        )
        .scalars()
        .all()
    )
    sum_1 = sum((c.amount for c in cells_1), Decimal("0"))
    sum_2 = sum((c.amount for c in cells_2), Decimal("0"))
    assert sum_1 == Decimal("3000")  # 3 × 1000 + budget remainder = 3000
    assert sum_2 == Decimal("3000")
    # Each cell is a manual_override (came from Excel).
    overrides_1 = [c for c in cells_1 if c.is_manual_override]
    overrides_2 = [c for c in cells_2 if c.is_manual_override]
    assert len(overrides_1) == 3
    assert len(overrides_2) == 3


@pytest.mark.asyncio
async def test_multi_project_ambiguous_cells_reported_not_imputed(db_session, _ensure_fixture):
    """When 2+ projects cover the SAME (y, m), neither receives the cell.
    The cell is reported as ambiguous so a human decides."""
    from datetime import date

    from sqlalchemy import select

    from app.core.models.project import ProjectDB
    from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB
    from scripts.import_accrual_spreadsheet import import_projects

    db_session.add(
        ProjectDB(
            name="overlapping A",
            code="OVR.LAP",
            status="live",
            currency="euro",
            is_billable=True,
            budget=Decimal("1500"),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
        )
    )
    db_session.add(
        ProjectDB(
            name="overlapping B",
            code="OVR.LAP",
            status="live",
            currency="euro",
            is_billable=True,
            budget=Decimal("1500"),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 3, 31),
        )
    )
    await db_session.flush()

    row = _multi_project_row(
        "OVR.LAP",
        {(2025, m): "500" for m in range(1, 4)},
    )
    report = await import_projects(db_session, [row])

    group = report["multi_project_groups"][0]
    assert group["ambiguous_cells"] == 3  # all 3 cells covered by BOTH projects
    assert group["orphan_cells"] == 0
    for proj in group["projects"]:
        assert proj["cells_imputed"] == 0  # nothing imputed when ambiguous

    # No manual_override cells exist (no Excel cell went through).
    ps = (
        (await db_session.execute(select(ProjectDB).where(ProjectDB.code == "OVR.LAP")))
        .scalars()
        .all()
    )
    for p in ps:
        cells = (
            (
                await db_session.execute(
                    select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == p.id)
                )
            )
            .scalars()
            .all()
        )
        assert not any(c.is_manual_override for c in cells), "no overrides applied"


@pytest.mark.asyncio
async def test_multi_project_orphan_cells_reported(db_session, _ensure_fixture):
    """Cells outside the date range of EVERY candidate are orphans."""
    from datetime import date

    from app.core.models.project import ProjectDB
    from scripts.import_accrual_spreadsheet import import_projects

    db_session.add(
        ProjectDB(
            name="phase 1",
            code="ORF.AN",
            status="live",
            currency="euro",
            is_billable=True,
            budget=Decimal("1000"),
            start_date=date(2025, 1, 1),
            end_date=date(2025, 2, 28),
        )
    )
    db_session.add(
        ProjectDB(
            name="phase 2",
            code="ORF.AN",
            status="live",
            currency="euro",
            is_billable=True,
            budget=Decimal("1000"),
            start_date=date(2025, 5, 1),
            end_date=date(2025, 6, 30),
        )
    )
    await db_session.flush()

    # Excel cells span Jan-Jun; Mar+Apr fall outside both project ranges.
    row = _multi_project_row(
        "ORF.AN",
        {(2025, m): "500" for m in range(1, 7)},
    )
    report = await import_projects(db_session, [row])

    group = report["multi_project_groups"][0]
    assert group["orphan_cells"] == 2  # Mar + Apr
    assert group["ambiguous_cells"] == 0
    total_imputed = sum(p["cells_imputed"] for p in group["projects"])
    assert total_imputed == 4  # Jan-Feb on phase 1, May-Jun on phase 2


@pytest.mark.asyncio
async def test_multi_project_original_budget_proportional_split(db_session, _ensure_fixture):
    """When N projects share a row, original_budget splits proportionally to
    each project's share of EUR imputed (only if currently NULL)."""
    from datetime import date

    from sqlalchemy import select

    from app.core.models.project import ProjectDB
    from scripts.import_accrual_spreadsheet import import_projects

    db_session.add(
        ProjectDB(
            name="big",
            code="SPLT.IT",
            status="live",
            currency="dollar",
            is_billable=True,
            budget=Decimal("3000"),
            original_budget=None,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 6, 30),
        )
    )
    db_session.add(
        ProjectDB(
            name="small",
            code="SPLT.IT",
            status="live",
            currency="dollar",
            is_billable=True,
            budget=Decimal("1000"),
            original_budget=None,
            start_date=date(2025, 7, 1),
            end_date=date(2025, 8, 31),
        )
    )
    await db_session.flush()

    # Excel 2025-01..2025-08, 500 EUR/month → 4000 EUR total. Big captures
    # 6 cells = 3000, small captures 2 cells = 1000. row.value = 4000 × 1.08 = 4320 USD.
    row = _multi_project_row(
        "SPLT.IT",
        {(2025, m): "500" for m in range(1, 9)},
    )
    report = await import_projects(db_session, [row])

    assert report["original_budget_set"] == 2
    ps = (
        (await db_session.execute(select(ProjectDB).where(ProjectDB.code == "SPLT.IT")))
        .scalars()
        .all()
    )
    big = next(p for p in ps if p.name == "big")
    small = next(p for p in ps if p.name == "small")
    # Big: 3000/4000 × 4320 = 3240 USD
    assert big.original_budget == Decimal("3240.00")
    # Small: 1000/4000 × 4320 = 1080 USD
    assert small.original_budget == Decimal("1080.00")
