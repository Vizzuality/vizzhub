"""Side-by-side comparison: Excel monthly cells vs DB project_accrual_cells.

Picks a sample of matched projects across currencies / years and prints a
mes-a-mes table for each, plus aggregate stats per project (total Excel sum
vs total DB sum, max absolute diff, max % diff).
"""

import asyncio
import importlib.util
import re
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.database import async_session_maker
from app.modules.accrual.models.project_accrual_cell import ProjectAccrualCellDB

SPREADSHEET = Path("/Users/miguelmendoza/Downloads/contract income tracker _as is_.xlsx")

# Load the importer module so we reuse its parsing + normalisation.
spec = importlib.util.spec_from_file_location(
    "imp_acc", Path(__file__).parent / "import_accrual_spreadsheet.py"
)
imp = importlib.util.module_from_spec(spec)
sys.modules["imp_acc"] = imp
spec.loader.exec_module(imp)  # type: ignore[attr-defined]


def _normalize(code: str | None) -> str | None:
    if not code:
        return None
    no_ws = "".join(code.split())
    return re.sub(r"\.{2,}", ".", no_ws).upper() or None


async def _load_db_cells(
    db: AsyncSession, project_ids: list
) -> dict[tuple, dict[tuple[int, int], dict]]:
    """Return {project_id: {(y,m): {amount, is_override, is_frozen}}}."""
    result = await db.execute(
        select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id.in_(project_ids))
    )
    out: dict = defaultdict(dict)
    for c in result.scalars():
        out[c.project_id][(c.year, c.month)] = {
            "amount": c.amount,
            "is_override": c.is_manual_override,
            "is_frozen": c.is_frozen,
        }
    return out


def _pct(a: Decimal, b: Decimal) -> Decimal | None:
    if b == 0:
        return None
    return ((a - b) / b * Decimal("100")).quantize(Decimal("0.01"))


async def main() -> None:
    print(f"Parsing {SPREADSHEET.name}...")
    raw = imp.parse_spreadsheet(SPREADSHEET)
    rows = imp.consolidate_duplicate_rows(raw)
    by_norm = {_normalize(r.code): r for r in rows if r.code}

    async with async_session_maker() as db:
        # Get all matched projects (those with original_budget set by the importer).
        result = await db.execute(select(ProjectDB).where(ProjectDB.original_budget.is_not(None)))
        projects = result.scalars().all()

        # Bucket projects by currency for sampling.
        by_currency: dict[str, list] = defaultdict(list)
        for p in projects:
            code = _normalize(p.code)
            if code in by_norm:
                by_currency[p.currency or "?"].append(p)

        print("Matched-project counts by currency:")
        for cur, plist in sorted(by_currency.items()):
            print(f"  {cur:6s} {len(plist):3d}")

        # Sample: take first 3 of each currency, plus the longest-running multi-year ones.
        sample = []
        for cur, plist in sorted(by_currency.items()):
            plist_sorted = sorted(
                plist,
                key=lambda p: (
                    -((p.end_date.year - p.start_date.year) if p.start_date and p.end_date else 0),
                    p.code or "",
                ),
            )
            sample.extend(plist_sorted[:3])

        print(f"\nSampling {len(sample)} projects.")
        db_cells = await _load_db_cells(db, [p.id for p in sample])

        summary: list[dict] = []
        for p in sample:
            norm = _normalize(p.code)
            row = by_norm.get(norm)
            if not row:
                continue
            excel_months = row.monthly
            db_months = db_cells.get(p.id, {})

            print("\n" + "=" * 90)
            print(
                f"{p.code}  |  {p.name[:50]:50s}  |  {p.currency or '?'}  "
                f"|  {p.start_date} → {p.end_date}"
            )
            print("-" * 90)
            print(f"{'Year-Month':<12}{'Excel':>14}{'DB':>14}{'Δ abs':>14}{'Δ %':>10}  flags")

            all_keys = sorted(set(excel_months) | set(db_months))
            tot_excel = Decimal("0")
            tot_db = Decimal("0")
            max_abs = Decimal("0")
            max_pct: Decimal | None = None
            n_match_exact = 0
            n_db_only = 0
            n_excel_only = 0
            for y, m in all_keys:
                exc = excel_months.get((y, m), Decimal("0"))
                dbc = db_months.get((y, m), {}).get("amount", Decimal("0"))
                tot_excel += exc
                tot_db += dbc
                diff = (dbc - exc).quantize(Decimal("0.01"))
                pct = _pct(dbc, exc)
                abs_d = abs(diff)
                if abs_d > max_abs:
                    max_abs = abs_d
                if pct is not None and (max_pct is None or abs(pct) > abs(max_pct)):
                    max_pct = pct
                if (y, m) in excel_months and (y, m) in db_months:
                    if abs_d < Decimal("0.05"):
                        n_match_exact += 1
                elif (y, m) in db_months:
                    n_db_only += 1
                else:
                    n_excel_only += 1

                flags = []
                meta = db_months.get((y, m))
                if meta and meta["is_override"]:
                    flags.append("override")
                if meta and meta["is_frozen"]:
                    flags.append("frozen")
                if (y, m) not in db_months:
                    flags.append("excel-only")
                if (y, m) not in excel_months:
                    flags.append("db-only")
                flag_str = ",".join(flags)

                pct_str = f"{pct:>9.2f}%" if pct is not None else "       —"
                print(
                    f"{y}-{m:02d}      "
                    f"{float(exc):>14,.2f}{float(dbc):>14,.2f}"
                    f"{float(diff):>14,.2f}{pct_str}  {flag_str}"
                )

            print("-" * 90)
            tot_diff = (tot_db - tot_excel).quantize(Decimal("0.01"))
            tot_pct = _pct(tot_db, tot_excel)
            tot_pct_str = f"{tot_pct:.2f}%" if tot_pct is not None else "—"
            print(
                f"TOTAL        {float(tot_excel):>14,.2f}{float(tot_db):>14,.2f}"
                f"{float(tot_diff):>14,.2f}      {tot_pct_str}  "
                f"(match_exact={n_match_exact} db_only={n_db_only} excel_only={n_excel_only})"
            )
            summary.append(
                {
                    "code": p.code,
                    "currency": p.currency,
                    "n_excel": len(excel_months),
                    "n_db": len(db_months),
                    "tot_excel": tot_excel,
                    "tot_db": tot_db,
                    "tot_diff": tot_diff,
                    "max_abs": max_abs,
                    "max_pct": max_pct,
                    "match_exact": n_match_exact,
                    "db_only": n_db_only,
                    "excel_only": n_excel_only,
                }
            )

        print("\n" + "#" * 90)
        print("SUMMARY")
        print("#" * 90)
        print(
            f"{'Code':<22}{'CCY':>5}{'#Exc':>6}{'#DB':>5}{'Σ Excel':>14}"
            f"{'Σ DB':>14}{'Δ Σ':>12}{'maxAbs':>11}{'maxΔ%':>9}  match"
        )
        for s in summary:
            mp = f"{s['max_pct']:>7.1f}%" if s["max_pct"] is not None else "      —"
            print(
                f"{s['code'][:22]:<22}{s['currency'] or '?':>5}"
                f"{s['n_excel']:>6}{s['n_db']:>5}"
                f"{float(s['tot_excel']):>14,.0f}{float(s['tot_db']):>14,.0f}"
                f"{float(s['tot_diff']):>12,.0f}{float(s['max_abs']):>11,.0f}{mp}  "
                f"x={s['match_exact']} dbo={s['db_only']} exo={s['excel_only']}"
            )


if __name__ == "__main__":
    asyncio.run(main())
