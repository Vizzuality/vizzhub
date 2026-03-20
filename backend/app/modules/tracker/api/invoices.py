"""Invoice CRUD and status transition endpoints."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.schemas.invoice import (
    ALLOWED_TRANSITIONS,
    InvoiceCreate,
    InvoiceResponse,
    InvoiceTransition,
    InvoiceUpdate,
)

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _effective_status(inv: InvoiceDB) -> str:
    if inv.status == "scheduled" and inv.due_date <= date.today():
        return "pending_to_issue"
    return inv.status


def _to_response(inv: InvoiceDB) -> InvoiceResponse:
    resp = InvoiceResponse.model_validate(inv)
    resp.status = _effective_status(inv)
    return resp


@router.get("/{project_id}/invoices")
async def list_invoices(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> list[InvoiceResponse]:
    stmt = (
        select(InvoiceDB)
        .where(InvoiceDB.project_id == project_id)
        .order_by(InvoiceDB.due_date.asc())
    )
    result = await db.execute(stmt)
    return [_to_response(inv) for inv in result.scalars().all()]


@router.post("/{project_id}/invoices", status_code=201)
async def create_invoice(
    project_id: UUID,
    body: InvoiceCreate,
    db: DBSession,
    user: CurrentUser,
) -> InvoiceResponse:
    inv = InvoiceDB(
        project_id=project_id,
        code=body.code,
        amount=Decimal(str(body.amount)),
        currency=body.currency,
        due_date=body.due_date,
        extended_date=body.extended_date,
        invoiced_on=body.invoiced_on,
        milestone=body.milestone,
        observations=body.observations,
        status=body.status,
    )
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return _to_response(inv)


@router.put("/{project_id}/invoices/{invoice_id}")
async def update_invoice(
    project_id: UUID,
    invoice_id: UUID,
    body: InvoiceUpdate,
    db: DBSession,
    user: CurrentUser,
) -> InvoiceResponse:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(404, "Invoice not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "amount" and value is not None:
            setattr(inv, field, Decimal(str(value)))
        else:
            setattr(inv, field, value)

    await db.commit()
    await db.refresh(inv)
    return _to_response(inv)


@router.post("/{project_id}/invoices/{invoice_id}/transition")
async def transition_invoice(
    project_id: UUID,
    invoice_id: UUID,
    body: InvoiceTransition,
    db: DBSession,
    user: CurrentUser,
) -> InvoiceResponse:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(404, "Invoice not found")

    effective = _effective_status(inv)
    allowed = ALLOWED_TRANSITIONS.get(effective, [])
    if body.status not in allowed:
        raise HTTPException(
            400,
            f"Cannot transition from '{inv.status}' to '{body.status}'. "
            f"Allowed: {', '.join(allowed)}",
        )

    if body.status == "paid" and not inv.code:
        raise HTTPException(
            400,
            "Invoice code is required before marking as paid",
        )

    inv.status = body.status
    await db.commit()
    await db.refresh(inv)
    return _to_response(inv)


@router.delete("/{project_id}/invoices/{invoice_id}", status_code=204)
async def delete_invoice(
    project_id: UUID,
    invoice_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> None:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(404, "Invoice not found")
    await db.delete(inv)
    await db.commit()
