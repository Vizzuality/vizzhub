"""Invoice postponement endpoints."""

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission

TrackerManager = Annotated[TokenData, Depends(require_permission(Action.TRACKER_MANAGE))]
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB
from app.modules.tracker.schemas.postponement import PostponeRequest, PostponementResponse
from app.modules.tracker.api.invoices import _invoice_status_info

router = APIRouter()

MAX_POSTPONE_DAYS = 30


@router.post(
    "/{project_id}/invoices/{invoice_id}/postpone",
    status_code=status.HTTP_201_CREATED,
)
async def postpone_invoice(
    project_id: UUID,
    invoice_id: UUID,
    body: PostponeRequest,
    db: DBSession,
    user: TrackerManager,
) -> PostponementResponse:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    eff, _, _ = await _invoice_status_info(inv, db)
    if eff != "pending_to_issue":
        raise HTTPException(status_code=400, detail="Only pending invoices can be postponed")

    result = await db.execute(
        select(InvoicePostponementDB.postponed_to)
        .where(InvoicePostponementDB.invoice_id == invoice_id)
        .order_by(InvoicePostponementDB.created_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    base_date = latest if latest is not None else inv.due_date

    today = date.today()
    window_base = max(base_date, today)

    if body.postponed_to <= base_date:
        raise HTTPException(
            status_code=400,
            detail=f"New date must be after {base_date}",
        )
    if body.postponed_to > window_base + timedelta(days=MAX_POSTPONE_DAYS):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot postpone more than {MAX_POSTPONE_DAYS} days from {window_base}",
        )

    postponement = InvoicePostponementDB(
        invoice_id=invoice_id,
        postponed_to=body.postponed_to,
        reason=body.reason,
        created_by=user.user_id,
    )
    db.add(postponement)
    await db.commit()
    await db.refresh(postponement)
    return PostponementResponse.model_validate(postponement)


@router.get("/{project_id}/invoices/{invoice_id}/postponements")
async def list_postponements(
    project_id: UUID,
    invoice_id: UUID,
    db: DBSession,
    user: TrackerManager,
) -> list[PostponementResponse]:
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    result = await db.execute(
        select(InvoicePostponementDB)
        .where(InvoicePostponementDB.invoice_id == invoice_id)
        .order_by(InvoicePostponementDB.created_at.desc())
    )
    return [PostponementResponse.model_validate(r) for r in result.scalars().all()]


@router.delete(
    "/{project_id}/invoices/{invoice_id}/postponements/latest",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_latest_postponement(
    project_id: UUID,
    invoice_id: UUID,
    db: DBSession,
    user: TrackerManager,
) -> None:
    """Delete the most recent postponement, reverting to previous date or due_date."""
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    result = await db.execute(
        select(InvoicePostponementDB)
        .where(InvoicePostponementDB.invoice_id == invoice_id)
        .order_by(InvoicePostponementDB.created_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        raise HTTPException(status_code=404, detail="No postponements to delete")

    await db.delete(latest)
    await db.commit()
