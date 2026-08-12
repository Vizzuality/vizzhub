"""Period management within the importer pipeline."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.services import period_service


async def bootstrap_periods(
    db: AsyncSession,
    *,
    current_year: int | None = None,
) -> list[AccrualPeriodDB]:
    """Create one accrual period (year boundary) per year spanned by billable DB projects.

    Periods are empty lifecycle markers (no fx_rates), so this just needs
    to cover Jan-1 of each year up to ``current_year``. Future cells live under
    the open period until the CEO creates the next period via the UI in due time.
    """
    proj_result = await db.execute(
        select(ProjectDB).where(
            ProjectDB.is_billable.is_(True),
            ProjectDB.start_date.is_not(None),
            ProjectDB.end_date.is_not(None),
        )
    )
    projects = list(proj_result.scalars().all())
    if not projects:
        return []

    if current_year is None:
        current_year = date.today().year
    min_year = min(min(p.start_date.year for p in projects), current_year)
    years = list(range(min_year, current_year + 1))

    created: list[AccrualPeriodDB] = []
    for y in years:
        existing = (
            await db.execute(
                select(AccrualPeriodDB).where(AccrualPeriodDB.start_date == date(y, 1, 1))
            )
        ).scalar_one_or_none()
        if existing is not None:
            created.append(existing)
            continue

        period = await period_service.create_period(
            db,
            start_date=date(y, 1, 1),
            created_by=None,
        )
        created.append(period)
    return created


async def freeze_historical_periods(db: AsyncSession) -> int:
    """Re-run the freeze pass on every closed period.

    Periods are created in bootstrap_periods before any cells exist, so the
    initial close freezes nothing. After cells are populated, this step
    retroactively freezes them.
    """
    result = await db.execute(
        select(AccrualPeriodDB)
        .where(AccrualPeriodDB.status == "closed")
        .order_by(AccrualPeriodDB.start_date)
    )
    total = 0
    for period in result.scalars().all():
        total += await period_service.freeze_period_cells(db, period_id=period.id)
    return total
