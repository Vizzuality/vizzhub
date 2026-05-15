"""Invoice CRUD and status transition endpoints."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission

logger = structlog.get_logger()

TrackerManager = Annotated[TokenData, Depends(require_permission(Action.TRACKER_MANAGE))]
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB
from app.modules.tracker.schemas.invoice import (
    ALLOWED_TRANSITIONS,
    InvoiceCreate,
    InvoiceResponse,
    InvoiceTransition,
    InvoiceUpdate,
)

from fastapi import APIRouter, HTTPException

router = APIRouter()

_INVOICE_NOT_FOUND = "Invoice not found"


from app.modules.tracker.services.invoice_status import (
    effective_status_expr as _effective_status_expr,
    postponement_subquery as _postponement_subquery,
)


async def _invoice_status_info(
    inv: InvoiceDB, db: AsyncSession
) -> tuple[str, int, date | None]:
    """Single query: return (effective_status, postpone_count, latest_postponed_to).

    ``latest_postponed_to`` is the ``postponed_to`` of the most recently
    *created* postponement (not the furthest-future one) — keeps this
    Python mirror semantically aligned with ``postponement_subquery``.
    """
    count_result = await db.execute(
        select(func.count()).where(InvoicePostponementDB.invoice_id == inv.id)
    )
    count = count_result.scalar() or 0

    latest_result = await db.execute(
        select(InvoicePostponementDB.postponed_to)
        .where(InvoicePostponementDB.invoice_id == inv.id)
        .order_by(InvoicePostponementDB.created_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()

    if inv.status in ("scheduled", "pending_to_issue") and latest is not None:
        eff = "postponed" if latest > date.today() else "pending_to_issue"
    elif inv.status == "scheduled" and inv.due_date <= date.today():
        eff = "pending_to_issue"
    else:
        eff = inv.status

    return eff, count, latest


async def _to_response(inv: InvoiceDB, db: AsyncSession) -> InvoiceResponse:
    eff, count, latest_pp = await _invoice_status_info(inv, db)
    return InvoiceResponse(
        id=inv.id,
        project_id=inv.project_id,
        code=inv.code,
        amount=float(inv.amount),
        due_date=inv.due_date,
        invoiced_on=inv.invoiced_on,
        milestone=inv.milestone,
        observations=inv.observations,
        status=eff,
        postpone_count=count,
        postponed_to=latest_pp if eff == "postponed" else None,
    )


@router.get("/{project_id}/invoices")
async def list_invoices(
    project_id: UUID,
    db: DBSession,
    user: TrackerManager,
) -> list[InvoiceResponse]:
    today = date.today()
    pp_sub = _postponement_subquery()
    eff_status = _effective_status_expr(today, pp_sub)

    stmt = (
        select(
            InvoiceDB,
            eff_status.label("eff_status"),
            func.coalesce(pp_sub.c.postpone_count, 0).label("pp_count"),
            pp_sub.c.postponed_to.label("pp_date"),
        )
        .outerjoin(pp_sub, pp_sub.c.invoice_id == InvoiceDB.id)
        .where(InvoiceDB.project_id == project_id)
        .order_by(InvoiceDB.due_date.asc())
    )
    result = await db.execute(stmt)
    return [
        InvoiceResponse(
            id=inv.id,
            project_id=inv.project_id,
            code=inv.code,
            amount=float(inv.amount),
            due_date=inv.due_date,
            invoiced_on=inv.invoiced_on,
            milestone=inv.milestone,
            observations=inv.observations,
            status=eff,
            postpone_count=pp_count,
            postponed_to=pp_date if eff == "postponed" else None,
        )
        for inv, eff, pp_count, pp_date in result.all()
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
