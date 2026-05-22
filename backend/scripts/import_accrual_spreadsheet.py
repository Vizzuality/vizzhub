#!/usr/bin/env python
"""One-shot importer for the CEO's accrual spreadsheet.

Reads the spreadsheet, creates historical periods seeded from observed rates,
autogenerates uniform cells for active Projects, and overlays per-row overrides
matched by Project.code.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


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


async def main_async(args: argparse.Namespace) -> int:
    print(
        f"[importer] spreadsheet={args.spreadsheet} dry_run={args.dry_run} periods_only={args.periods_only}"
    )
    if not args.spreadsheet.exists():
        print(f"[importer] file not found: {args.spreadsheet}", file=sys.stderr)
        return 1
    # Subsequent tasks fill in the implementation.
    return 0


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
