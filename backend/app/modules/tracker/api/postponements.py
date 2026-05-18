"""Invoice postponement endpoints — request / approve / reject / cancel flow.

Postponements are *requests* that must be approved by an admin before they
take effect on the invoice. The state machine on a postponement row:

    pending --approve--> approved   (date becomes effective)
            --reject---> rejected   (no effect; audit trail preserved)
            --cancel---> cancelled  (requester withdrew)
"""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.permissions import Action, require_permission
from app.modules.notifications.models.slack import AlertDefinitionDB
from app.modules.notifications.services.alert_service import AlertService
from app.modules.notifications.services.slack_service import SlackService
from app.modules.tracker.api.invoices import _invoice_status_info
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB
from app.modules.tracker.schemas.postponement import (
    PostponementDecision,
    PostponementResponse,
    PostponeRequest,
)
from app.utils.slack import get_slack_bot_token

TrackerManager = Annotated[TokenData, Depends(require_permission(Action.TRACKER_MANAGE))]
AdminUser = Annotated[TokenData, Depends(require_permission("*"))]

logger = structlog.get_logger()

_INVOICE_NOT_FOUND = "Invoice not found"
_POSTPONEMENT_NOT_FOUND = "Postponement not found"

router = APIRouter()

MAX_POSTPONE_DAYS = 30
HUB_BASE_URL = "https://hub.vizzuality.com"


def _detail_url(invoice_id: UUID) -> str:
    return f"{HUB_BASE_URL}/admin/tracker/invoices/{invoice_id}"


async def _user_display_name(db: AsyncSession, user_id: UUID | None) -> str:
    if user_id is None:
        return "Someone"
    row = await db.execute(
        select(
            func.coalesce(
                func.nullif(
                    func.trim(func.concat_ws(" ", UserDB.first_name, UserDB.last_name)),
                    "",
                ),
                UserDB.name,
                func.split_part(UserDB.email, "@", 1),
            )
        ).where(UserDB.id == user_id)
    )
    name = row.scalar_one_or_none()
    return name or "Someone"


async def _user_slack_id(db: AsyncSession, user_id: UUID | None) -> str | None:
    if user_id is None:
        return None
    row = await db.execute(select(UserDB.slack_user_id).where(UserDB.id == user_id))
    return row.scalar_one_or_none()


async def _approver_recipient(db: AsyncSession) -> tuple[str, UUID] | None:
    """Return (slack_user_id, alert_definition_id) for the approver, if configured."""
    result = await db.execute(
        select(AlertDefinitionDB).where(
            AlertDefinitionDB.name == "invoice_postponed",
            AlertDefinitionDB.is_enabled.is_(True),
        )
    )
    alert_def = result.scalar_one_or_none()
    if not alert_def:
        return None
    recipient = (alert_def.config_json or {}).get("recipient_slack_user_id", "")
    if not recipient:
        return None
    return recipient, alert_def.id


async def _send_dm(
    db: AsyncSession,
    *,
    invoice: InvoiceDB,
    recipient: str,
    message: str,
    alert_def_id: UUID | None,
    metadata: dict,
) -> None:
    bot_token = await get_slack_bot_token(db)
    if not bot_token:
        return
    slack_result = await SlackService.send_message(
        bot_token, recipient, message, unfurl_links=False,
    )
    if alert_def_id is not None:
        await AlertService.log_notification(
            db,
            project_id=invoice.project_id,
            alert_definition_id=alert_def_id,
            channel_id=recipient,
            message=message,
            status="sent" if slack_result.get("ok") else "failed",
            error_message=slack_result.get("error") if not slack_result.get("ok") else None,
            metadata=metadata,
        )


async def _notify_approver(
    db: AsyncSession,
    *,
    invoice: InvoiceDB,
    postponement: InvoicePostponementDB,
    message: str,
    kind: str,
    log_event: str,
    extra_metadata: dict | None = None,
) -> None:
    """DM the configured approver about a request/cancellation, swallowing failures."""
    try:
        approver = await _approver_recipient(db)
        if approver is None:
            return
        recipient, alert_def_id = approver
        metadata = {"kind": kind, "postponement_id": str(postponement.id)}
        if extra_metadata:
            metadata.update(extra_metadata)
        await _send_dm(
            db,
            invoice=invoice,
            recipient=recipient,
            message=message,
            alert_def_id=alert_def_id,
            metadata=metadata,
        )
    except Exception:
        logger.exception(log_event)


async def _notify_request(
    db: AsyncSession,
    invoice: InvoiceDB,
    project_name: str,
    postponement: InvoicePostponementDB,
) -> None:
    requester_name = await _user_display_name(db, postponement.created_by)
    message = (
        f":hourglass: *Postpone request* from {requester_name}\n"
        f"*Project:* {project_name}\n"
        f"*Invoice:* {invoice.milestone}\n"
        f"*Current due:* {invoice.due_date}\n"
        f"*Proposed:* {postponement.postponed_to}\n"
        f"*Reason:* {postponement.reason}\n"
        f"<{_detail_url(invoice.id)}|Open invoice to approve or reject>"
    )
    await _notify_approver(
        db,
        invoice=invoice,
        postponement=postponement,
        message=message,
        kind="postpone_requested",
        log_event="postpone_request_notification_failed",
        extra_metadata={"proposed_to": str(postponement.postponed_to)},
    )


async def _notify_decision(
    db: AsyncSession,
    invoice: InvoiceDB,
    project_name: str,
    postponement: InvoicePostponementDB,
    decision: str,
) -> None:
    """Notify the requester after approve/reject."""
    try:
        slack_id = await _user_slack_id(db, postponement.created_by)
        if not slack_id:
            return
        approver_name = await _user_display_name(db, postponement.decided_by)
        emoji = ":white_check_mark:" if decision == "approved" else ":x:"
        body = (
            f"{emoji} *Postpone {decision}* by {approver_name}\n"
            f"*Project:* {project_name}\n"
            f"*Invoice:* {invoice.milestone}\n"
            f"*Proposed:* {postponement.postponed_to}\n"
        )
        if postponement.decision_note:
            body += f"*Note:* {postponement.decision_note}\n"
        body += f"<{_detail_url(invoice.id)}|Open invoice>"
        await _send_dm(
            db,
            invoice=invoice,
            recipient=slack_id,
            message=body,
            alert_def_id=None,
            metadata={
                "kind": f"postpone_{decision}",
                "postponement_id": str(postponement.id),
            },
        )
    except Exception:
        logger.exception("postpone_decision_notification_failed")


async def _notify_cancellation(
    db: AsyncSession,
    invoice: InvoiceDB,
    project_name: str,
    postponement: InvoicePostponementDB,
) -> None:
    """Notify approver when requester cancels their pending request."""
    requester_name = await _user_display_name(db, postponement.created_by)
    message = (
        f":no_entry_sign: *Postpone request cancelled* by {requester_name}\n"
        f"*Project:* {project_name}\n"
        f"*Invoice:* {invoice.milestone}\n"
        f"*Proposed had been:* {postponement.postponed_to}"
    )
    await _notify_approver(
        db,
        invoice=invoice,
        postponement=postponement,
        message=message,
        kind="postpone_cancelled",
        log_event="postpone_cancellation_notification_failed",
    )


async def _load_pending_postponement(
    db: AsyncSession,
    project_id: UUID,
    invoice_id: UUID,
    postponement_id: UUID,
    verb: str,
) -> tuple[InvoiceDB, InvoicePostponementDB]:
    """Resolve invoice + postponement for a decision endpoint, enforcing the pending guard."""
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail=_INVOICE_NOT_FOUND)

    pp = await db.get(InvoicePostponementDB, postponement_id)
    if not pp or pp.invoice_id != invoice_id:
        raise HTTPException(status_code=404, detail=_POSTPONEMENT_NOT_FOUND)
    if pp.approval_status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Postponement is {pp.approval_status}, only pending requests can be {verb}",
        )
    return inv, pp


async def _project_name(db: AsyncSession, project_id: UUID) -> str:
    project = await db.get(ProjectDB, project_id)
    return project.name if project else "Unknown"


async def _latest_approved_postponed_to(
    db: AsyncSession, invoice_id: UUID
) -> date | None:
    """Date of the most recently approved postponement, if any."""
    result = await db.execute(
        select(InvoicePostponementDB.postponed_to)
        .where(
            InvoicePostponementDB.invoice_id == invoice_id,
            InvoicePostponementDB.approval_status == "approved",
        )
        .order_by(InvoicePostponementDB.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _has_pending_postponement(db: AsyncSession, invoice_id: UUID) -> bool:
    result = await db.execute(
        select(func.count()).where(
            InvoicePostponementDB.invoice_id == invoice_id,
            InvoicePostponementDB.approval_status == "pending",
        )
    )
    return (result.scalar() or 0) > 0


@router.post(
    "/{project_id}/invoices/{invoice_id}/postpone",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invoice not eligible or date out of range"},
        404: {"description": "Invoice not found"},
        409: {"description": "A pending postpone request already exists"},
    },
)
async def postpone_invoice(
    project_id: UUID,
    invoice_id: UUID,
    body: PostponeRequest,
    db: DBSession,
    user: TrackerManager,
) -> PostponementResponse:
    """Create a pending postpone request. Approval is required for it to take effect."""
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail=_INVOICE_NOT_FOUND)

    if await _has_pending_postponement(db, invoice_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A postpone request is already pending approval",
        )

    eff, _, _ = await _invoice_status_info(inv, db)
    if eff not in ("scheduled", "pending_to_issue"):
        raise HTTPException(
            status_code=400,
            detail="Only scheduled or pending invoices can be postponed",
        )

    latest_approved = await _latest_approved_postponed_to(db, invoice_id)
    base_date = latest_approved if latest_approved is not None else inv.due_date
    window_base = max(base_date, date.today())

    if body.postponed_to <= window_base:
        raise HTTPException(
            status_code=400,
            detail="New date must be after today and after the current due/postponed date",
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
        approval_status="pending",
    )
    db.add(postponement)
    await db.flush()
    await db.refresh(postponement)

    await _notify_request(db, inv, await _project_name(db, project_id), postponement)
    logger.info(
        "invoice_postpone_requested",
        invoice_id=str(invoice_id),
        project_id=str(project_id),
        postponement_id=str(postponement.id),
        user_id=user.user_id,
        proposed_to=str(body.postponed_to),
    )

    return PostponementResponse.model_validate(postponement)


@router.post(
    "/{project_id}/invoices/{invoice_id}/postponements/{postponement_id}/approve",
    responses={
        400: {"description": "Postponement is not pending"},
        404: {"description": "Invoice or postponement not found"},
    },
)
async def approve_postponement(
    project_id: UUID,
    invoice_id: UUID,
    postponement_id: UUID,
    db: DBSession,
    user: AdminUser,
    body: PostponementDecision | None = None,
) -> PostponementResponse:
    inv, pp = await _load_pending_postponement(
        db, project_id, invoice_id, postponement_id, verb="approved"
    )

    pp.approval_status = "approved"
    pp.decided_by = user.user_id
    pp.decided_at = datetime.now(UTC)
    pp.decision_note = body.note if body else None
    await db.flush()
    await db.refresh(pp)

    await _notify_decision(db, inv, await _project_name(db, project_id), pp, "approved")
    logger.info(
        "invoice_postpone_approved",
        invoice_id=str(invoice_id),
        postponement_id=str(postponement_id),
        user_id=user.user_id,
    )

    return PostponementResponse.model_validate(pp)


@router.post(
    "/{project_id}/invoices/{invoice_id}/postponements/{postponement_id}/reject",
    responses={
        400: {"description": "Postponement is not pending or note missing"},
        404: {"description": "Invoice or postponement not found"},
    },
)
async def reject_postponement(
    project_id: UUID,
    invoice_id: UUID,
    postponement_id: UUID,
    body: PostponementDecision,
    db: DBSession,
    user: AdminUser,
) -> PostponementResponse:
    if not body.note or not body.note.strip():
        raise HTTPException(status_code=400, detail="A rejection note is required")

    inv, pp = await _load_pending_postponement(
        db, project_id, invoice_id, postponement_id, verb="rejected"
    )

    pp.approval_status = "rejected"
    pp.decided_by = user.user_id
    pp.decided_at = datetime.now(UTC)
    pp.decision_note = body.note.strip()
    await db.flush()
    await db.refresh(pp)

    await _notify_decision(db, inv, await _project_name(db, project_id), pp, "rejected")
    logger.info(
        "invoice_postpone_rejected",
        invoice_id=str(invoice_id),
        postponement_id=str(postponement_id),
        user_id=user.user_id,
    )

    return PostponementResponse.model_validate(pp)


@router.post(
    "/{project_id}/invoices/{invoice_id}/postponements/{postponement_id}/cancel",
    responses={
        400: {"description": "Postponement is not pending"},
        403: {"description": "Only the requester (or an admin) can cancel"},
        404: {"description": "Invoice or postponement not found"},
    },
)
async def cancel_postponement(
    project_id: UUID,
    invoice_id: UUID,
    postponement_id: UUID,
    db: DBSession,
    user: TrackerManager,
) -> PostponementResponse:
    inv, pp = await _load_pending_postponement(
        db, project_id, invoice_id, postponement_id, verb="cancelled"
    )

    is_admin = "*" in (user.permissions or [])
    if pp.created_by != user.user_id and not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Only the requester or an admin can cancel a postpone request",
        )

    pp.approval_status = "cancelled"
    pp.decided_by = user.user_id
    pp.decided_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(pp)

    await _notify_cancellation(db, inv, await _project_name(db, project_id), pp)
    logger.info(
        "invoice_postpone_cancelled",
        invoice_id=str(invoice_id),
        postponement_id=str(postponement_id),
        user_id=user.user_id,
    )

    return PostponementResponse.model_validate(pp)


@router.get(
    "/{project_id}/invoices/{invoice_id}/postponements",
    responses={404: {"description": "Invoice not found"}},
)
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
    decider = aliased(UserDB)

    def _display_name(alias):
        return func.coalesce(
            func.nullif(
                func.trim(func.concat_ws(" ", alias.first_name, alias.last_name)),
                "",
            ),
            alias.name,
            func.split_part(alias.email, "@", 1),
        )

    result = await db.execute(
        select(
            InvoicePostponementDB,
            _display_name(creator).label("creator_name"),
            _display_name(decider).label("decider_name"),
        )
        .outerjoin(creator, InvoicePostponementDB.created_by == creator.id)
        .outerjoin(decider, InvoicePostponementDB.decided_by == decider.id)
        .where(InvoicePostponementDB.invoice_id == invoice_id)
        .order_by(InvoicePostponementDB.created_at.desc())
    )
    rows = result.all()
    return [
        PostponementResponse(
            **{
                **PostponementResponse.model_validate(p).model_dump(),
                "created_by_name": creator_name,
                "decided_by_name": decider_name,
            }
        )
        for p, creator_name, decider_name in rows
    ]


@router.delete(
    "/{project_id}/invoices/{invoice_id}/postponements/latest",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        400: {"description": "Latest postponement is not approved"},
        404: {"description": "Invoice or postponement not found"},
    },
)
async def delete_latest_postponement(
    project_id: UUID,
    invoice_id: UUID,
    db: DBSession,
    user: TrackerManager,
) -> None:
    """Delete the most recent *approved* postponement, reverting to previous date or due_date.

    Pending / cancelled / rejected postponements are not removable this way —
    use the approve / reject / cancel endpoints to resolve them instead.
    """
    inv = await db.get(InvoiceDB, invoice_id)
    if not inv or inv.project_id != project_id:
        raise HTTPException(status_code=404, detail=_INVOICE_NOT_FOUND)

    if inv.status in ("paid", "voided"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot remove postponement: invoice is {inv.status} and "
                "no longer eligible for postponement edits."
            ),
        )

    result = await db.execute(
        select(InvoicePostponementDB)
        .where(
            InvoicePostponementDB.invoice_id == invoice_id,
            InvoicePostponementDB.approval_status == "approved",
        )
        .order_by(InvoicePostponementDB.created_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        raise HTTPException(status_code=404, detail="No approved postponements to delete")

    await db.delete(latest)
    logger.info(
        "invoice_postponement_deleted",
        invoice_id=str(invoice_id),
        project_id=str(project_id),
        user_id=user.user_id,
    )
