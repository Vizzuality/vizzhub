"""Derive a project's EUR budget + accrual line from its original (contract) budget.

FX arithmetic lives here (accrual domain): the start-date period rate is the
source of truth, ECB is the fallback, EUR is a passthrough. Conversion follows
the ECB convention used platform-wide: rate = foreign units per €1, so
value_eur = original_budget / rate.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.services.exchange_rate_service import currency_to_code, get_latest_rate
from app.modules.accrual.models.accrual_cell import AccrualCellDB, CellSource
from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from app.modules.accrual.services import cell_service, period_service

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


def _months_between(start: date, end: date) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return out


def _is_derivable(project: ProjectDB) -> bool:
    return (
        project.original_budget is not None
        and bool(project.currency)
        and project.start_date is not None
        and project.end_date is not None
    )


async def _find_derived_line(db: AsyncSession, project_id: UUID) -> AccrualLineDB | None:
    """The single team_budget line linked to this project, if any."""
    result = await db.execute(
        select(AccrualLineDB)
        .join(AccrualLineProjectDB, AccrualLineProjectDB.line_id == AccrualLineDB.id)
        .where(
            AccrualLineProjectDB.project_id == project_id,
            AccrualLineDB.source == LineSource.TEAM_BUDGET.value,
        )
    )
    return result.scalars().first()


async def _refresh_derived_line(
    db: AsyncSession,
    line: AccrualLineDB,
    *,
    value_eur: Decimal,
    rate: Decimal | None,
) -> AccrualLineDB:
    """Recompute value/rate and redistribute open months only (R4); window is
    sovereign (R5) — never re-derived from project dates here."""
    line.value_eur = value_eur
    line.rate = rate
    await db.flush()

    frozen_total = sum(
        (
            c.amount
            for c in (
                await db.execute(
                    select(AccrualCellDB).where(
                        AccrualCellDB.line_id == line.id, AccrualCellDB.is_frozen.is_(True)
                    )
                )
            )
            .scalars()
            .all()
        ),
        Decimal("0"),
    )
    if frozen_total > value_eur:
        logger.warning(
            "accrual_line_budget_underwater",
            line_id=str(line.id),
            value_eur=str(value_eur),
            frozen_total=str(frozen_total),
        )

    await cell_service.redistribute_for_line(
        db, line_id=line.id, force=False, source=CellSource.TEAM_BUDGET
    )
    logger.info("accrual_derived_line_refreshed", line_id=str(line.id), value_eur=str(value_eur))
    return line


async def upsert_derived_line(db: AsyncSession, *, project_id: UUID) -> AccrualLineDB | None:
    """Build or refresh the project's derived team_budget line.

    Non-derivable (missing any of original_budget/currency/start_date/end_date,
    or no FX rate) -> no-op, returns None. Create seeds window=project dates +
    uniform spread. (Update path is added in the next task.)
    """
    project = await db.get(ProjectDB, project_id)
    if project is None or not _is_derivable(project):
        return None
    value_eur = await convert_original_budget(
        db,
        original_budget=Decimal(project.original_budget),
        currency=project.currency,
        start_date=project.start_date,
    )
    if value_eur is None:
        return None
    code = currency_to_code(project.currency)
    rate = None if code == "EUR" else await _resolve_rate(db, code, project.start_date)

    existing = await _find_derived_line(db, project_id)
    if existing is not None:
        return await _refresh_derived_line(db, existing, value_eur=value_eur, rate=rate)

    line = AccrualLineDB(
        id=uuid4(),
        name=project.name,
        source=LineSource.TEAM_BUDGET.value,
        excel_code=project.code,
        value_orig=Decimal(project.original_budget),
        currency=code,
        rate=rate,
        value_eur=value_eur,
        window_start=project.start_date,
        window_end=project.end_date,
    )
    db.add(line)
    await db.flush()
    db.add(AccrualLineProjectDB(line_id=line.id, project_id=project_id))
    months = _months_between(project.start_date, project.end_date)
    per_month = _quantize(value_eur / Decimal(len(months)))
    for y, m in months:
        db.add(
            AccrualCellDB(
                line_id=line.id,
                year=y,
                month=m,
                amount=per_month,
                is_manual_override=False,
                is_frozen=False,
                source=CellSource.TEAM_BUDGET.value,
            )
        )
    await db.flush()
    logger.info(
        "accrual_derived_line_created",
        line_id=str(line.id),
        project_id=str(project_id),
        value_eur=str(value_eur),
        months=len(months),
    )
    return line
