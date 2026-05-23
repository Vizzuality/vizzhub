"""Migration script integration tests."""

import subprocess
import sys
from decimal import Decimal
from pathlib import Path

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


import pytest


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
