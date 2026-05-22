"""Resolve EUR conversion rate for an accrual cell.

Resolution order, first hit wins:
1. project.locked_fx_rate (per-project manual override).
2. project.currency normalises to EUR → Decimal('1').
3. Active period for (year, month) has the currency → period.fx_rates[code].
4. ECB rate stored on/before the first of the month.
5. None — caller must decide how to surface unresolved cells.

``projects.currency`` historically stores lowercase human labels ("dollar",
"euro") rather than ISO 4217 codes; we route through ``currency_to_code``
so live data resolves alongside the freshly-typed ISO codes.
"""

from datetime import date
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.services.exchange_rate_service import currency_to_code, get_latest_rate
from app.modules.accrual.services import period_service

logger = structlog.get_logger()


async def resolve_rate(
    db: AsyncSession,
    *,
    project: ProjectDB,
    year: int,
    month: int,
) -> Decimal | None:
    """Return the EUR conversion rate for a project in the given month.

    Returns ``None`` when no rate can be determined; callers should surface
    unresolved cells rather than silently using a wrong value.
    """
    if project.locked_fx_rate is not None:
        return project.locked_fx_rate

    raw = (project.currency or "").strip()
    if not raw:
        return None
    code = currency_to_code(raw)
    if code == "EUR":
        return Decimal("1")

    period = await period_service.get_period_for_month(db, year=year, month=month)
    if period is not None and code in period.fx_rates:
        return Decimal(period.fx_rates[code])

    ecb = await get_latest_rate(db, code, as_of=date(year, month, 1))
    if ecb is None:
        logger.warning(
            "accrual_fx_unresolved",
            project_id=str(project.id),
            currency=code,
            year=year,
            month=month,
        )
        return None
    rate, _ = ecb
    return rate
