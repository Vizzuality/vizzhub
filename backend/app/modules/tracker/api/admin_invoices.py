"""Admin invoice listing with filters, search, sorting, and pagination."""

import datetime as dt
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from sqlalchemy import func, select, case, literal

from app.core.api.deps import AdminUser, DBSession
from app.core.models.exchange_rate import ExchangeRateDB
from app.core.models.project import ProjectDB
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


def _postponement_subquery():
    """Latest postponed_to + count per invoice."""
    return (
        select(
            InvoicePostponementDB.invoice_id,
            func.max(InvoicePostponementDB.postponed_to).label("postponed_to"),
            func.count().label("postpone_count"),
        )
        .group_by(InvoicePostponementDB.invoice_id)
        .subquery()
    )


def _effective_status_expr(today, pp_sub):
    """SQL case expression for effective status with postponement support."""
    return case(
        (
            InvoiceDB.status.in_(["scheduled", "pending_to_issue"])
            & pp_sub.c.postponed_to.isnot(None)
            & (pp_sub.c.postponed_to > today),
            literal("postponed"),
        ),
        (
            InvoiceDB.status.in_(["scheduled", "pending_to_issue"])
            & pp_sub.c.postponed_to.isnot(None)
            & (pp_sub.c.postponed_to <= today),
            literal("pending_to_issue"),
        ),
        (
            (InvoiceDB.status == "scheduled") & (InvoiceDB.due_date <= today),
            literal("pending_to_issue"),
        ),
        else_=InvoiceDB.status,
    )


def _apply_filters(
    stmt,
    status: str | None,
    project_id: UUID | None,
    search: str | None,
    due_from: dt.date | None,
    due_to: dt.date | None,
    today: dt.date,
    pp_sub,
):
    if status:
        if status == "pending_to_issue":
            stmt = stmt.where(
                ((InvoiceDB.status == "pending_to_issue") |
                 ((InvoiceDB.status == "scheduled") & (InvoiceDB.due_date <= today)))
                & (pp_sub.c.postponed_to.is_(None) | (pp_sub.c.postponed_to <= today))
            )
        elif status == "postponed":
            stmt = stmt.where(
                InvoiceDB.status.in_(["scheduled", "pending_to_issue"])
                & pp_sub.c.postponed_to.isnot(None)
                & (pp_sub.c.postponed_to > today)
            )
        elif status == "scheduled":
            stmt = stmt.where(
                (InvoiceDB.status == "scheduled")
                & (InvoiceDB.due_date > today)
                & (pp_sub.c.postponed_to.is_(None) | (pp_sub.c.postponed_to <= today))
            )
        else:
            stmt = stmt.where(InvoiceDB.status == status)

    if project_id:
        stmt = stmt.where(InvoiceDB.project_id == project_id)
    if search:
        stmt = stmt.where(ProjectDB.name.ilike(f"%{search}%"))
    if due_from:
        stmt = stmt.where(InvoiceDB.due_date >= due_from)
    if due_to:
        stmt = stmt.where(InvoiceDB.due_date <= due_to)

    return stmt


class AdminInvoiceResponse(BaseModel):
    id: UUID
    project_id: UUID
    project_name: str
    code: str | None
    amount: float
    currency: str
    due_date: dt.date
    invoiced_on: dt.date | None
    milestone: str
    observations: str | None
    status: str
    postpone_count: int
    postponed_to: dt.date | None


class PaginatedInvoicesResponse(BaseModel):
    items: list[AdminInvoiceResponse]
    total: int
    page: int
    pages: int


class InvoiceTotalsResponse(BaseModel):
    total_pending_eur: float
    total_postponed_eur: float
    total_waiting_eur: float
    total_current_year_eur: float
    usd_eur_rate: float | None
    rate_date: dt.date | None


@router.get("/totals")
async def get_invoice_totals(
    db: DBSession,
    user: AdminUser,
) -> InvoiceTotalsResponse:
    """KPI totals for admin invoices — all amounts normalized to EUR."""
    today = dt.date.today()
    current_year = today.year

    pp_sub = _postponement_subquery()
    effective_status = _effective_status_expr(today, pp_sub)

    currency_code_expr = case(
        (ProjectDB.currency == "dollar", literal("USD")),
        (ProjectDB.currency == "euro", literal("EUR")),
        else_=func.upper(ProjectDB.currency),
    )

    latest_rate = (
        select(
            ExchangeRateDB.currency_code,
            ExchangeRateDB.rate,
        )
        .distinct(ExchangeRateDB.currency_code)
        .order_by(ExchangeRateDB.currency_code, ExchangeRateDB.rate_date.desc())
        .subquery()
    )

    stmt = (
        select(
            InvoiceDB.amount,
            currency_code_expr.label("cur_code"),
            effective_status.label("eff_status"),
            InvoiceDB.due_date,
            latest_rate.c.rate,
        )
        .join(ProjectDB, InvoiceDB.project_id == ProjectDB.id)
        .outerjoin(pp_sub, pp_sub.c.invoice_id == InvoiceDB.id)
        .outerjoin(latest_rate, latest_rate.c.currency_code == currency_code_expr)
    )

    result = await db.execute(stmt)
    rows = result.all()

    total_pending = Decimal("0")
    total_postponed = Decimal("0")
    total_waiting = Decimal("0")
    total_year = Decimal("0")

    for amount, cur_code, eff_status, due_date, rate in rows:
        if cur_code == "EUR" or not rate:
            eur_amount = amount
        else:
            eur_amount = amount / rate

        if eff_status == "pending_to_issue":
            total_pending += eur_amount
        elif eff_status == "postponed":
            total_postponed += eur_amount
        elif eff_status == "waiting_for_payment":
            total_waiting += eur_amount

        if due_date.year == current_year:
            total_year += eur_amount

    usd_result = await db.execute(
        select(ExchangeRateDB.rate, ExchangeRateDB.rate_date)
        .where(ExchangeRateDB.currency_code == "USD")
        .order_by(ExchangeRateDB.rate_date.desc())
        .limit(1)
    )
    usd_row = usd_result.first()

    return InvoiceTotalsResponse(
        total_pending_eur=round(float(total_pending), 2),
        total_postponed_eur=round(float(total_postponed), 2),
        total_waiting_eur=round(float(total_waiting), 2),
        total_current_year_eur=round(float(total_year), 2),
        usd_eur_rate=float(usd_row.rate) if usd_row else None,
        rate_date=usd_row.rate_date if usd_row else None,
    )


@router.get("")
async def list_all_invoices(
    db: DBSession,
    user: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    status: Annotated[str | None, Query()] = None,
    project_id: Annotated[UUID | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    due_from: Annotated[dt.date | None, Query()] = None,
    due_to: Annotated[dt.date | None, Query()] = None,
    sort_by: Annotated[str, Query()] = "status",
    sort_order: Annotated[str, Query()] = "asc",
) -> PaginatedInvoicesResponse:
    today = dt.date.today()
    pp_sub = _postponement_subquery()
    effective_status = _effective_status_expr(today, pp_sub)

    base = (
        select(
            InvoiceDB,
            ProjectDB.name.label("project_name"),
            ProjectDB.currency.label("project_currency"),
            effective_status.label("eff_status"),
            func.coalesce(pp_sub.c.postpone_count, 0).label("pp_count"),
            pp_sub.c.postponed_to.label("pp_date"),
        )
        .join(ProjectDB, InvoiceDB.project_id == ProjectDB.id)
        .outerjoin(pp_sub, pp_sub.c.invoice_id == InvoiceDB.id)
    )

    base = _apply_filters(base, status, project_id, search, due_from, due_to, today, pp_sub)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    status_order = case(
        {
            "pending_to_issue": 0,
            "postponed": 1,
            "waiting_for_payment": 2,
            "scheduled": 3,
            "paid": 4,
        },
        value=effective_status,
        else_=5,
    )

    paid_last = case(
        (effective_status == "paid", 1),
        else_=0,
    )

    if sort_by == "project":
        order_col = ProjectDB.name
    elif sort_by == "due_date":
        order_col = InvoiceDB.due_date
    elif sort_by == "amount":
        order_col = InvoiceDB.amount
    else:
        order_col = status_order

    if sort_by == "due_date":
        if sort_order == "desc":
            base = base.order_by(paid_last.asc(), order_col.desc())
        else:
            base = base.order_by(paid_last.asc(), order_col.asc())
    elif sort_order == "desc":
        base = base.order_by(order_col.desc(), InvoiceDB.due_date.asc())
    else:
        base = base.order_by(order_col.asc(), InvoiceDB.due_date.asc())

    offset = (page - 1) * page_size
    base = base.offset(offset).limit(page_size)

    result = await db.execute(base)
    rows = result.all()

    items = [
        AdminInvoiceResponse(
            id=inv.id,
            project_id=inv.project_id,
            project_name=project_name,
            code=inv.code,
            amount=float(inv.amount),
            currency=project_currency,
            due_date=inv.due_date,
            invoiced_on=inv.invoiced_on,
            milestone=inv.milestone,
            observations=inv.observations,
            status=eff_status,
            postpone_count=pp_count,
            postponed_to=pp_date if eff_status == "postponed" else None,
        )
        for inv, project_name, project_currency, eff_status, pp_count, pp_date in rows
    ]

    pages = max(1, (total + page_size - 1) // page_size)

    return PaginatedInvoicesResponse(items=items, total=total, page=page, pages=pages)
