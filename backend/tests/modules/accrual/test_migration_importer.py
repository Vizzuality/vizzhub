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
