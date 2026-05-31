"""Derive a project's EUR budget + accrual line from its original (contract) budget.

FX arithmetic lives here (accrual domain): the start-date period rate is the
source of truth, ECB is the fallback, EUR is a passthrough. Conversion follows
the ECB convention used platform-wide: rate = foreign units per €1, so
value_eur = original_budget / rate.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.exchange_rate_service import currency_to_code, get_latest_rate
from app.modules.accrual.services import period_service

logger = structlog.get_logger()


def _quantize(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def _resolve_rate(db: AsyncSession, code: str, start_date: date) -> Decimal | None:
    """Foreign-per-€ rate for ``code`` at ``start_date``: period rate first, ECB fallback.

    EUR is handled by the caller (passthrough). Returns None when neither the
    start-date period nor ECB has a usable (non-zero) rate.
    """
    period = await period_service.get_period_for_month(
        db, year=start_date.year, month=start_date.month
    )
    if period and code in period.fx_rates:
        rate = Decimal(str(period.fx_rates[code]))
        if rate != 0:
            return rate
    ecb = await get_latest_rate(db, code, as_of=start_date)
    if ecb is not None and ecb[0] != 0:
        return ecb[0]
    return None


async def convert_original_budget(
    db: AsyncSession,
    *,
    original_budget: Decimal,
    currency: str,
    start_date: date,
) -> Decimal | None:
    """EUR value of ``original_budget`` using the start-date period rate.

    Read-only. EUR passthrough; period rate → ECB fallback. Returns None when no
    rate is available — the caller treats that as non-derivable (no-op).
    """
    code = currency_to_code(currency)
    if code == "EUR":
        return _quantize(original_budget)
    rate = await _resolve_rate(db, code, start_date)
    if rate is None:
        logger.warning("accrual_derive_no_rate", currency=code, start_date=start_date.isoformat())
        return None
    return _quantize(original_budget / rate)
