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
async def test_import_extends_dates_when_excel_exceeds_db(db_session, _ensure_fixture):
    """When merged Excel rows extend beyond DB project dates, project range is widened."""
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
    # Dates extended to encompass both amendments.
    assert project.start_date == date(2024, 1, 1)
    assert project.end_date == date(2026, 12, 1)
    # original_budget = sum of both rows (12k + 12k).
    assert project.original_budget == Decimal("24000")
    assert report["dates_extended"] == 1


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
    from decimal import Decimal

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
    # B001 starts 2024 with USD rate=1.1 → median is 1.1.
    assert Decimal(p_2024.fx_rates["USD"]).normalize() == Decimal("1.1")
    # EUR is implicit / passthrough — no key.
    assert "EUR" not in p_2024.fx_rates


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
    # locked_fx_rate untouched.
    assert p.locked_fx_rate is None

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
