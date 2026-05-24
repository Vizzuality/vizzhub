#!/usr/bin/env python
"""One-shot importer for the CEO's accrual spreadsheet.

Thin CLI wrapper around ``app.modules.accrual.services.importer.run_pipeline``.
Existing names (``SpreadsheetRow``, ``parse_spreadsheet``, ``import_projects``,
``bootstrap_periods``, ``_normalize_code``, ``_code_prefix``,
``consolidate_duplicate_rows``) are re-exported here for backward compatibility
with existing tests.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure ``backend/`` is on sys.path when invoked directly (e.g. ``python
# scripts/import_accrual_spreadsheet.py``) — otherwise the ``app.*`` imports
# below fail.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Re-export the importer surface for backward compatibility with existing tests
# and external callers that still import from ``scripts.import_accrual_spreadsheet``.
from app.modules.accrual.services.importer import (  # noqa: F401, E402
    SpreadsheetRow,
    _code_prefix,
    _normalize_code,
    bootstrap_periods,
    consolidate_duplicate_rows,
    freeze_historical_periods,
    import_projects,
    parse_spreadsheet,
    run_pipeline,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spreadsheet", required=True, type=Path)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--periods-only",
        action="store_true",
        help="Stop after creating historical periods (review rates before full import).",
    )
    return p.parse_args(argv)


class _DryRun(Exception):
    """Sentinel to trigger db.begin() rollback for --dry-run."""


async def main_async(args: argparse.Namespace) -> int:
    if not args.spreadsheet.exists():
        print(f"[importer] file not found: {args.spreadsheet}", file=sys.stderr)
        return 1

    from app.database import async_session_maker

    rows = parse_spreadsheet(args.spreadsheet)
    consolidated = consolidate_duplicate_rows(rows)
    print(
        f"[importer] parsed {len(rows)} rows ({len(rows) - len(consolidated)} duplicates "
        f"consolidated into amendments) from {args.spreadsheet}"
    )

    async with async_session_maker() as db:
        try:
            async with db.begin():
                if args.periods_only:
                    periods = await bootstrap_periods(db, rows)
                    print(f"[importer] created {len(periods)} periods")
                    if args.dry_run:
                        raise _DryRun()
                    return 0
                report = await run_pipeline(
                    db,
                    rows=consolidated,
                    source_path=str(args.spreadsheet),
                )
                frozen = await freeze_historical_periods(db)
                print(f"[importer] {report} | frozen_cells={frozen}")
                if args.dry_run:
                    raise _DryRun()
        except _DryRun:
            print("[importer] dry-run complete — rolled back", file=sys.stderr)
    return 0


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
