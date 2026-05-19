"""Invoice CRUD and status transition endpoints."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB
from app.modules.tracker.schemas.invoice import (
    ALLOWED_TRANSITIONS,
    InvoiceCreate,
    InvoiceResponse,
    InvoiceTransition,
    InvoiceUpdate,
)
from app.modules.tracker.services.invoice_status import (
    approved_postponement_subquery,
    effective_status_expr,
    latest_postponement_subquery,
)

logger = structlog.get_logger()

TrackerManager = Annotated[TokenData, Depends(require_permission(Action.TRACKER_MANAGE))]

router = APIRouter()

_INVOICE_NOT_FOUND = "Invoice not found"


async def _invoice_status_info(inv: InvoiceDB, db: AsyncSession) -> tuple[str, int, date | None]:
    """Return (effective_status, approved_postpone_count, latest_approved_postponed_to).

    Python mirror of ``effective_status_expr`` for single-invoice endpoints.
    """
    pp_result = await db.execute(
        select(InvoicePostponementDB)
        .where(InvoicePostponementDB.invoice_id == inv.id)
        .order_by(InvoicePostponementDB.created_at.desc())
    )
    pps = list(pp_result.scalars().all())
    latest = pps[0] if pps else None
    latest_approved = next((p for p in pps if p.approval_status == "approved"), None)
    approved_count = sum(1 for p in pps if p.approval_status == "approved")

    today = date.today()
    if latest is not None and latest.approval_status == "pending":
        eff = "postpone_pending"
    elif inv.status in ("scheduled", "pending_to_issue") and latest_approved is not None:
        eff = "postponed" if latest_approved.postponed_to > today else "pending_to_issue"
    elif inv.status == "scheduled" and inv.due_date <= today:
        eff = "pending_to_issue"
    else:
        eff = inv.status

    return eff, approved_count, latest_approved.postponed_to if latest_approved else None


def _build_response(
    inv: InvoiceDB, eff_status: str, pp_count: int, pp_date: date | None
) -> InvoiceResponse:
    """Assemble an ``InvoiceResponse`` from an invoice + computed status fields."""
    return InvoiceResponse(
        id=inv.id,
        project_id=inv.project_id,
        code=inv.code,
        amount=float(inv.amount),
        due_date=inv.due_date,
        invoiced_on=inv.invoiced_on,
        milestone=inv.milestone,
        observations=inv.observations,
        invoicing_contact_name=inv.invoicing_contact_name,
        invoicing_contact_email=inv.invoicing_contact_email,
        status=eff_status,
        postpone_count=pp_count,
        postponed_to=pp_date if eff_status == "postponed" else None,
    )


async def _to_response(inv: InvoiceDB, db: AsyncSession) -> InvoiceResponse:
    eff, count, latest_pp = await _invoice_status_info(inv, db)
    return _build_response(inv, eff, count, latest_pp)


@router.get("/{project_id}/invoices")
async def list_invoices(
    project_id: UUID,
    db: DBSession,
    user: TrackerManager,
) -> list[InvoiceResponse]:
    today = date.today()
    latest_pp = latest_postponement_subquery()
    approved_pp = approved_postponement_subquery()
    eff_status = effective_status_expr(today, latest_pp, approved_pp)

    stmt = (
        select(
            InvoiceDB,
            eff_status.label("eff_status"),
            func.coalesce(approved_pp.c.approved_count, 0).label("pp_count"),
            approved_pp.c.approved_postponed_to.label("pp_date"),
        )
        .outerjoin(latest_pp, latest_pp.c.invoice_id == InvoiceDB.id)
        .outerjoin(approved_pp, approved_pp.c.invoice_id == InvoiceDB.id)
        .where(InvoiceDB.project_id == project_id)
        .order_by(InvoiceDB.due_date.asc())
    )
    result = await db.execute(stmt)
    return [
        _build_response(inv, eff, pp_count, pp_date) for inv, eff, pp_count, pp_date in result.all()
    ]


@router.post("/{project_id}/invoices", status_code=201)
async def create_invoice(
    project_id: UUID,
    body: InvoiceCreate,
    db: DBSession,
    user: TrackerManager,
) -> InvoiceResponse:
    inv = InvoiceDB(
        project_id=project_id,
        code=body.code,
        amount=Decimal(str(body.amount)),
        due_date=body.due_date,
        invoiced_on=body.invoiced_on,
        milestone=body.milestone,
        observations=body.observations,
        invoicing_contact_name=body.invoicing_contact_name,
        invoicing_contact_email=body.invoicing_contact_email,
        status=body.status,
    )
    db.add(inv)
    await db.flush()
    await db.refresh(inv)
    logger.info(
        "invoice_created",
        invoice_id=str(inv.id),
        project_id=str(project_id),
        user_id=user.user_id,
        amount=float(inv.amount),
    )
    return await _to_response(inv, db)


@router.put(
    "/{project_id}/invoices/{invoice_id}",
    responses={404: {"description": "Invoice not found"}},
)
async def update_invoice(
    project_id: UUID,
    invoice_id: UUID,
    body: InvoiceUpdate,
    db: DBSession,
    user: TrackerManager,
) -> InvoiceResponse:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(404, _INVOICE_NOT_FOUND)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "amount" and value is not None:
            setattr(inv, field, Decimal(str(value)))
        else:
            setattr(inv, field, value)

    await db.flush()
    await db.refresh(inv)
    return await _to_response(inv, db)


@router.post(
    "/{project_id}/invoices/{invoice_id}/transition",
    responses={
        400: {"description": "Invalid transition or missing invoice code"},
        404: {"description": "Invoice not found"},
    },
)
async def transition_invoice(
    project_id: UUID,
    invoice_id: UUID,
    body: InvoiceTransition,
    db: DBSession,
    user: TrackerManager,
) -> InvoiceResponse:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(404, _INVOICE_NOT_FOUND)

    effective, _, _ = await _invoice_status_info(inv, db)
    if effective == "postponed":
        raise HTTPException(400, "Cannot transition a postponed invoice")

    allowed = ALLOWED_TRANSITIONS.get(effective, [])
    if body.status not in allowed:
        raise HTTPException(
            400,
            f"Cannot transition from '{effective}' to '{body.status}'. "
            f"Allowed: {', '.join(allowed)}",
        )

    if body.status == "paid" and not inv.code:
        raise HTTPException(
            400,
            "Invoice code is required before marking as paid",
        )

    previous_status = inv.status
    inv.status = body.status
    await db.flush()
    await db.refresh(inv)
    logger.info(
        "invoice_status_transitioned",
        invoice_id=str(invoice_id),
        project_id=str(project_id),
        user_id=user.user_id,
        previous_status=previous_status,
        new_status=body.status,
    )
    return await _to_response(inv, db)


@router.delete(
    "/{project_id}/invoices/{invoice_id}",
    status_code=204,
    responses={404: {"description": "Invoice not found"}},
)
async def delete_invoice(
    project_id: UUID,
    invoice_id: UUID,
    db: DBSession,
    user: TrackerManager,
) -> None:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(404, _INVOICE_NOT_FOUND)
    await db.delete(inv)
    await db.flush()
    logger.info(
        "invoice_deleted",
        invoice_id=str(invoice_id),
        project_id=str(project_id),
        user_id=user.user_id,
    )
