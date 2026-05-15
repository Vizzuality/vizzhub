"""Recalculate global_metrics history end-to-end.

Use this after a deploy that changes scoring logic or adds new global_metrics
columns (e.g., audit #17: budget-weighted columns introduced 2026-05-15).

What it does:
    1. Finds the earliest MetricsDB period across the database.
    2. Calls GlobalMetricsService.calculate_batch from that month to today.
    3. This re-aggregates every month using the CURRENT scoring logic,
       repopulating equal-weighted AND budget-weighted columns.

What it does NOT do:
    - Re-capture raw metrics from GitHub/Jira/etc. The MetricsDB rows
      are read as-is. To regenerate raw data, use recapture_all_projects.py
      instead.

Usage (production via docker exec):
    docker exec hub-backend python scripts/recalc_global_history.py

Expected runtime: ~1-2 seconds per month. A year of history finishes in
under a minute.
"""

import asyncio
import sys
from datetime import date

from sqlalchemy import select

from app.config import get_scoring_config
from app.database import async_session_maker
from app.modules.scorecard.models.metrics import MetricsDB
from app.modules.scorecard.services.global_metrics_service import GlobalMetricsService


async def main() -> int:
    config = get_scoring_config()
    service = GlobalMetricsService(config)

    async with async_session_maker() as db:
        result = await db.execute(
            select(MetricsDB.period_year, MetricsDB.period_month)
            .order_by(MetricsDB.period_year.asc(), MetricsDB.period_month.asc())
            .limit(1)
        )
        earliest = result.first()

        if earliest is None:
            print("No MetricsDB rows found — nothing to recalculate.")
            return 0

        from_year, from_month = earliest
        today = date.today()
        to_year, to_month = today.year, today.month

        print(
            f"Recalculating global_metrics from {from_year:04d}-{from_month:02d} "
            f"to {to_year:04d}-{to_month:02d}..."
        )

        try:
            records = await service.calculate_batch(
                db, from_year, from_month, to_year, to_month
            )
        except Exception as exc:
            print(f"FAILED during calculate_batch: {exc!r}", file=sys.stderr)
            return 1

        non_empty = sum(1 for r in records if r.project_count > 0)
        with_budget = sum(
            1
            for r in records
            if getattr(r, "budget_weighted_project_count", 0) and r.budget_weighted_project_count > 0
        )

        print(f"Done. {len(records)} months processed.")
        print(f"  - {non_empty} months with at least one project.")
        print(f"  - {with_budget} months with at least one budgeted project.")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
