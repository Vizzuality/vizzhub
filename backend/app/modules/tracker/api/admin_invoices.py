"""Admin invoice listing with filters, search, sorting, and pagination."""

import datetime as dt
from typing import Annotated
from uuid import UUID

from sqlalchemy import func, select, case, literal
from sqlalchemy.orm import aliased

from app.core.api.deps import AdminUser, DBSession
from app.core.models.project import ProjectDB
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.api.invoices import _effective_status

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class AdminInvoiceResponse(BaseModel):
    id: UUID
    project_id: UUID
    project_name: str
    code: str | None
    amount: float
    due_date: dt.date
    extended_date: dt.date | None
    invoiced_on: dt.date | None
    milestone: str
    observations: str | None
    status: str


class PaginatedInvoicesResponse(BaseModel):
    items: list[AdminInvoiceResponse]
    total: int
    page: int
    pages: int


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

    effective_status = case(
        (
            (InvoiceDB.status == "scheduled") & (InvoiceDB.due_date <= today),
            literal("pending_to_issue"),
        ),
        else_=InvoiceDB.status,
    )

    base = (
        select(InvoiceDB, ProjectDB.name.label("project_name"), effective_status.label("eff_status"))
        .join(ProjectDB, InvoiceDB.project_id == ProjectDB.id)
    )

    if status:
        if status == "pending_to_issue":
            base = base.where(
                ((InvoiceDB.status == "pending_to_issue") |
                 ((InvoiceDB.status == "scheduled") & (InvoiceDB.due_date <= today)))
            )
        elif status == "scheduled":
            base = base.where(
                (InvoiceDB.status == "scheduled") & (InvoiceDB.due_date > today)
            )
        else:
            base = base.where(InvoiceDB.status == status)

    if project_id:
        base = base.where(InvoiceDB.project_id == project_id)

    if search:
        base = base.where(ProjectDB.name.ilike(f"%{search}%"))

    if due_from:
        base = base.where(InvoiceDB.due_date >= due_from)
    if due_to:
        base = base.where(InvoiceDB.due_date <= due_to)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    status_order = case(
        {
            "pending_to_issue": 0,
            "waiting_for_payment": 1,
            "scheduled": 2,
            "paid": 3,
        },
        value=effective_status,
        else_=4,
    )

    if sort_by == "project":
        order_col = ProjectDB.name
    elif sort_by == "due_date":
        order_col = InvoiceDB.due_date
    elif sort_by == "amount":
        order_col = InvoiceDB.amount
    else:
        order_col = status_order

    if sort_order == "desc":
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
            due_date=inv.due_date,
            extended_date=inv.extended_date,
            invoiced_on=inv.invoiced_on,
            milestone=inv.milestone,
            observations=inv.observations,
            status=eff_status,
        )
        for inv, project_name, eff_status in rows
    ]

    pages = max(1, (total + page_size - 1) // page_size)

    return PaginatedInvoicesResponse(items=items, total=total, page=page, pages=pages)
