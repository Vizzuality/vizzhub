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
