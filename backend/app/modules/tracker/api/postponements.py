"""Invoice postponement endpoints."""

import logging
from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.permissions import Action, require_permission
from app.modules.scorecard.models.slack import AlertDefinitionDB
from app.modules.scorecard.services.alert_service import AlertService
from app.modules.scorecard.services.slack_service import SlackService
from app.modules.tracker.api.invoices import _invoice_status_info
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB
from app.modules.tracker.schemas.postponement import PostponeRequest, PostponementResponse
from app.utils.slack import get_slack_bot_token

TrackerManager = Annotated[TokenData, Depends(require_permission(Action.TRACKER_MANAGE))]

logger = logging.getLogger(__name__)

_INVOICE_NOT_FOUND = "Invoice not found"

router = APIRouter()

MAX_POSTPONE_DAYS = 30
HUB_BASE_URL = "https://hub.vizzuality.com"


async def _notify_postponement(
    db: AsyncSession,
    invoice: InvoiceDB,
    project_name: str,
    new_date: date,
    reason: str,
) -> None:
    """Send Slack DM to configured recipient when an invoice is postponed."""
    try:
        result = await db.execute(
            select(AlertDefinitionDB).where(
                AlertDefinitionDB.name == "invoice_postponed",
                AlertDefinitionDB.is_enabled.is_(True),
            )
        )
        alert_def = result.scalar_one_or_none()
        if not alert_def:
            return

        recipient = (alert_def.config_json or {}).get("recipient_slack_user_id", "")
        if not recipient:
            return

        bot_token = await get_slack_bot_token(db)
        if not bot_token:
            return

        template = await AlertService.get_template(db, alert_def.id, "initial")
        if not template:
            return

        detail_url = f"{HUB_BASE_URL}/admin/tracker/invoices/{invoice.id}"
        message = AlertService.render_template(template, {
            "project_name": project_name,
            "due_date": str(invoice.due_date),
            "new_date": str(new_date),
            "reason": reason,
            "detail_url": detail_url,
        })

        slack_result = await SlackService.send_message(
            bot_token, recipient, message, unfurl_links=False,
        )

        await AlertService.log_notification(
            db,
            project_id=invoice.project_id,
            alert_definition_id=alert_def.id,
            channel_id=recipient,
            message=message,
            status="sent" if slack_result.get("ok") else "failed",
            error_message=slack_result.get("error") if not slack_result.get("ok") else None,
            metadata={"new_date": str(new_date), "due_date": str(invoice.due_date)},
        )
    except Exception:
        logger.exception("Failed to send invoice postponement notification")


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
        raise HTTPException(status_code=404, detail=_INVOICE_NOT_FOUND)

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

    project = await db.get(ProjectDB, project_id)
    project_name = project.name if project else "Unknown"
    await _notify_postponement(db, inv, project_name, body.postponed_to, body.reason)

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
        raise HTTPException(status_code=404, detail=_INVOICE_NOT_FOUND)

    creator = aliased(UserDB)
    name_expr = func.coalesce(
        func.nullif(
            func.trim(func.concat_ws(" ", creator.first_name, creator.last_name)),
            "",
        ),
        creator.name,
        func.split_part(creator.email, "@", 1),
    )
    result = await db.execute(
        select(InvoicePostponementDB, name_expr.label("creator_name"))
        .outerjoin(creator, InvoicePostponementDB.created_by == creator.id)
        .where(InvoicePostponementDB.invoice_id == invoice_id)
        .order_by(InvoicePostponementDB.created_at.desc())
    )
    rows = result.all()
    return [
        PostponementResponse(
            **{
                **PostponementResponse.model_validate(p).model_dump(),
                "created_by_name": creator_name,
            }
        )
        for p, creator_name in rows
    ]


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
        raise HTTPException(status_code=404, detail=_INVOICE_NOT_FOUND)

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
