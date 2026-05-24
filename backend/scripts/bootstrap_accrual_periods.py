"""One-shot bootstrap of accrual_periods covering the billable project range.

Creates one period per year boundary (Jan-1) from the earliest billable project
start year up to the current calendar year. ``period_service.create_period``
auto-closes the previous open period when a new one is created, so iterating
chronologically yields N-1 closed periods + 1 open period — same shape as the
production lifecycle.

Idempotent: re-running skips periods whose ``start_date`` is already present.

Usage:
    cd backend && PYTHONPATH=. uv run python scripts/bootstrap_accrual_periods.py
    cd backend && PYTHONPATH=. uv run python scripts/bootstrap_accrual_periods.py --min-year 2016
"""

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

import structlog

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.models.project import ProjectDB
from app.database import async_session_maker
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.services import period_service

logger = structlog.get_logger()


async def infer_min_year(db) -> int:
    """Earliest start year across billable projects with both dates set."""
    result = await db.execute(
        select(ProjectDB.start_date).where(
            ProjectDB.is_billable.is_(True),
            ProjectDB.start_date.is_not(None),
            ProjectDB.end_date.is_not(None),
        )
    )
    years = [d.year for d in result.scalars().all() if d is not None]
    if not years:
        raise SystemExit("No billable projects with start_date — refusing to bootstrap.")
    return min(years)


async def main(min_year_arg: int | None) -> None:
    today = date.today()
    current_year = today.year

    async with async_session_maker() as db:
        min_year = min_year_arg or await infer_min_year(db)
        if min_year > current_year:
            raise SystemExit(f"min_year={min_year} is in the future")

        existing_result = await db.execute(
            select(AccrualPeriodDB.start_date).order_by(AccrualPeriodDB.start_date)
        )
        existing = {d for d in existing_result.scalars().all()}
        logger.info(
            "bootstrap_starting",
            min_year=min_year,
            current_year=current_year,
            existing_count=len(existing),
        )

        created = 0
        skipped = 0
        for year in range(min_year, current_year + 1):
            start = date(year, 1, 1)
            if start in existing:
                skipped += 1
                continue
            try:
                period = await period_service.create_period(db, start_date=start, created_by=None)
            except period_service.PeriodConflictError as exc:
                logger.warning("bootstrap_conflict", start_date=str(start), error=str(exc))
                skipped += 1
                continue
            created += 1
            logger.info(
                "bootstrap_period_created",
                start_date=str(start),
                period_id=str(period.id),
            )

        await db.commit()
        logger.info("bootstrap_completed", created=created, skipped=skipped)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Earliest year to bootstrap (default: min(project.start_date.year))",
    )
    args = parser.parse_args()
    asyncio.run(main(args.min_year))
