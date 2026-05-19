"""Daily invoice alert checks.

Fires three kinds of Slack notifications based on each invoice's *effective*
scheduled date (original due_date, or the latest approved postpone date if
still in the future). For ``postpone_pending`` rows the original due_date is
used — the pending request has no effect until an admin approves.

Alert kinds:
- ``advance_30d`` — DM the project's PM up to 30 days before the effective date.
- ``advance_15d`` — DM the project's PM up to 15 days before the effective date.
- ``issue_reminder`` — ping the configured issuer in the configured channel
  one day before the effective date.

Dedup uses ``AlertNotificationDB.metadata_json`` (invoice_id, fired_for_date,
alert_kind) via ``AlertService.was_invoice_alert_sent``. When an approved
postpone shifts the effective date, the new ``fired_for_date`` has no match
and the alert fires for the new date — exactly the re-fire semantics we
want.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.notifications.models.slack import AlertDefinitionDB
from app.modules.notifications.services.alert_service import AlertService
from app.modules.notifications.services.slack_service import SlackService
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB
from app.utils.slack import get_slack_bot_token
from app.worker.utils import complete_job_run, complete_with_error, start_job_run

logger = structlog.get_logger()

HUB_BASE_URL = "https://hub.vizzuality.com"

ALERT_ADVANCE = "invoice_advance_warning"
ALERT_ISSUE = "invoice_issue_reminder"

KIND_30D = "advance_30d"
KIND_15D = "advance_15d"
KIND_ISSUE = "issue_reminder"

# Invoice raw statuses where an alert could still apply. ``paid`` and
# ``waiting_for_payment`` already moved past the issue moment.
ELIGIBLE_RAW_STATUSES = ("scheduled", "pending_to_issue")


@dataclass(slots=True)
class InvoiceContext:
    invoice: InvoiceDB
    project: ProjectDB
    effective_date: date
    days_until: int


def _detail_url(invoice_id: UUID) -> str:
    return f"{HUB_BASE_URL}/admin/tracker/invoices/{invoice_id}"


def _format_amount(invoice: InvoiceDB) -> str:
    """Render the amount without trailing zeros for whole numbers."""
    amount = float(invoice.amount)
    if amount.is_integer():
        return f"{int(amount):,}"
    return f"{amount:,.2f}"


def _currency_label(project: ProjectDB) -> str:
    mapping = {"dollar": "USD", "euro": "EUR"}
    return mapping.get(project.currency, project.currency.upper())


async def _effective_date_for(db: AsyncSession, invoice: InvoiceDB, today: date) -> date | None:
    """Return the effective scheduled date for this invoice.

    Returns ``None`` when the invoice is not in an alertable state
    (raw status not in eligible set, or its effective state is already
    past the issue moment).
    """
    if invoice.status not in ELIGIBLE_RAW_STATUSES:
        return None

    result = await db.execute(
        select(InvoicePostponementDB)
        .where(InvoicePostponementDB.invoice_id == invoice.id)
        .order_by(InvoicePostponementDB.created_at.desc())
    )
    postponements = list(result.scalars().all())

    latest_approved = next((p for p in postponements if p.approval_status == "approved"), None)
    if latest_approved is not None and latest_approved.postponed_to > today:
        return latest_approved.postponed_to

    # postpone_pending and rejected/cancelled fall through to the original.
    return invoice.due_date


async def _candidate_contexts(
    db: AsyncSession, today: date, horizon_days: int = 30
) -> list[InvoiceContext]:
    """Invoices whose effective date is within ``horizon_days`` of today."""
    result = await db.execute(
        select(InvoiceDB, ProjectDB)
        .join(ProjectDB, InvoiceDB.project_id == ProjectDB.id)
        .where(InvoiceDB.status.in_(ELIGIBLE_RAW_STATUSES))
    )
    contexts: list[InvoiceContext] = []
    for invoice, project in result.all():
        effective = await _effective_date_for(db, invoice, today)
        if effective is None:
            continue
        days_until = (effective - today).days
        if days_until < 0 or days_until > horizon_days:
            continue
        contexts.append(
            InvoiceContext(
                invoice=invoice,
                project=project,
                effective_date=effective,
                days_until=days_until,
            )
        )
    return contexts


def _build_context(ctx: InvoiceContext) -> dict[str, Any]:
    inv = ctx.invoice
    return {
        "project_name": ctx.project.name,
        "milestone": inv.milestone or inv.code or "Untitled milestone",
        "amount": _format_amount(inv),
        "currency": _currency_label(ctx.project),
        "due_date": ctx.effective_date.isoformat(),
        "days_until": ctx.days_until,
        "detail_url": _detail_url(inv.id),
    }


async def _dispatch_alert(
    db: AsyncSession,
    ctx: InvoiceContext,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    *,
    kind: str,
    target_channel: str,
    extra_metadata: dict[str, Any] | None = None,
    post_render: Callable[[str], str] | None = None,
) -> bool:
    """Run the shared dedup → template → send → log → commit pipeline.

    Callers handle gating (days_until, recipient resolution) and pass in the
    resolved channel/user id plus any kind-specific metadata. ``post_render``
    lets a caller splice non-escapable content (e.g. raw ``<@id>`` mentions)
    into the rendered message before sending.
    """
    if await AlertService.was_invoice_alert_sent(
        db, alert_def.id, ctx.invoice.id, ctx.effective_date, kind
    ):
        return False

    template = await AlertService.get_template(db, alert_def.id, "initial")
    if not template:
        logger.warning("invoice_alert_no_template", alert=alert_def.name)
        return False

    message = AlertService.render_template(template, _build_context(ctx))
    if post_render is not None:
        message = post_render(message)

    metadata: dict[str, Any] = {
        "invoice_id": str(ctx.invoice.id),
        "fired_for_date": ctx.effective_date.isoformat(),
        "alert_kind": kind,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    response = await SlackService.send_message(bot_token, target_channel, message)
    ok = bool(response.get("ok"))
    await AlertService.log_notification(
        db=db,
        project_id=ctx.project.id,
        alert_definition_id=alert_def.id,
        channel_id=target_channel,
        message=message,
        status="sent" if ok else "failed",
        error_message=None if ok else response.get("error"),
        metadata=metadata,
    )
    if ok:
        await db.commit()
        logger.info(
            "invoice_alert_sent",
            invoice_id=str(ctx.invoice.id),
            project=ctx.project.name,
            kind=kind,
            days_until=ctx.days_until,
        )
    return ok


async def _fire_advance(
    db: AsyncSession,
    ctx: InvoiceContext,
    alert_def: AlertDefinitionDB,
    bot_token: str,
    threshold: int,
    kind: str,
) -> bool:
    """DM the project manager once per (invoice, effective date, kind)."""
    if ctx.days_until > threshold:
        return False

    pm_id = ctx.project.project_manager_id
    if pm_id is None:
        logger.info(
            "invoice_alert_skipped_no_pm",
            invoice_id=str(ctx.invoice.id),
            project=ctx.project.name,
            kind=kind,
        )
        return False

    pm = await db.get(UserDB, pm_id)
    if pm is None or not pm.slack_user_id:
        logger.info(
            "invoice_alert_skipped_pm_no_slack",
            invoice_id=str(ctx.invoice.id),
            project=ctx.project.name,
            kind=kind,
        )
        return False

    return await _dispatch_alert(
        db,
        ctx,
        alert_def,
        bot_token,
        kind=kind,
        target_channel=pm.slack_user_id,
        extra_metadata={"threshold_days": threshold, "days_until": ctx.days_until},
    )


async def _fire_issue_reminder(
    db: AsyncSession,
    ctx: InvoiceContext,
    alert_def: AlertDefinitionDB,
    bot_token: str,
) -> bool:
    """Post to the configured channel pinging the configured issuer."""
    if ctx.days_until != 1:
        return False

    cfg = alert_def.config_json or {}
    channel_id = cfg.get("recipient_slack_channel_id")
    issuer_id = cfg.get("recipient_slack_user_id")
    if not channel_id or not issuer_id:
        logger.info(
            "invoice_alert_skipped_missing_config",
            invoice_id=str(ctx.invoice.id),
            kind=KIND_ISSUE,
            has_channel=bool(channel_id),
            has_issuer=bool(issuer_id),
        )
        return False

    # Splice the raw <@id> mention after rendering. The mrkdwn escaper in
    # render_template would otherwise mangle <, @, > and any underscore in
    # the ID, killing the mention.
    return await _dispatch_alert(
        db,
        ctx,
        alert_def,
        bot_token,
        kind=KIND_ISSUE,
        target_channel=channel_id,
        extra_metadata={"issuer_slack_user_id": issuer_id},
        post_render=lambda msg: msg.replace("{issuer}", issuer_id),
    )


async def _get_alert_definitions(db: AsyncSession) -> dict[str, AlertDefinitionDB]:
    result = await db.execute(
        select(AlertDefinitionDB).where(
            AlertDefinitionDB.name.in_([ALERT_ADVANCE, ALERT_ISSUE]),
            AlertDefinitionDB.is_enabled.is_(True),
        )
    )
    return {d.name: d for d in result.scalars().all()}


ADVANCE_STEPS: tuple[tuple[int, str], ...] = ((30, KIND_30D), (15, KIND_15D))


async def _process_candidate(
    db: AsyncSession,
    inv_ctx: InvoiceContext,
    advance_def: AlertDefinitionDB | None,
    issue_def: AlertDefinitionDB | None,
    bot_token: str,
) -> int:
    """Fire every applicable alert for a single invoice; return alerts sent.

    Wrapped by the orchestrator in a try/except so a single bad row can
    rollback its own changes and not poison the rest of the run.
    """
    sent = 0
    if advance_def is not None:
        for threshold, kind in ADVANCE_STEPS:
            if await _fire_advance(db, inv_ctx, advance_def, bot_token, threshold, kind):
                sent += 1
    if issue_def is not None and await _fire_issue_reminder(db, inv_ctx, issue_def, bot_token):
        sent += 1
    return sent


async def check_invoice_alerts(ctx: dict) -> dict[str, Any]:
    """Send invoice advance warnings and issue reminders."""
    db: AsyncSession = ctx["db"]
    job_run = await start_job_run(db, "check_invoice_alerts")
    logger.info("job_started", job_name="check_invoice_alerts", job_run_id=str(job_run.id))

    try:
        bot_token = await get_slack_bot_token(db)
        if not bot_token:
            return await complete_with_error(
                db, job_run, "Slack not configured - missing bot token"
            )

        definitions = await _get_alert_definitions(db)
        if not definitions:
            return await complete_with_error(db, job_run, "No enabled invoice alert definitions")

        today = date.today()
        candidates = await _candidate_contexts(db, today)
        logger.info("invoice_candidates_found", count=len(candidates))

        invoices_checked = 0
        alerts_sent = 0
        advance_def = definitions.get(ALERT_ADVANCE)
        issue_def = definitions.get(ALERT_ISSUE)

        for inv_ctx in candidates:
            # Capture identifiers up-front: a rollback in the except branch
            # expires ORM attributes, so reading them lazily would raise.
            invoice_id = inv_ctx.invoice.id
            project_name = inv_ctx.project.name
            try:
                alerts_sent += await _process_candidate(
                    db, inv_ctx, advance_def, issue_def, bot_token
                )
            except Exception:
                await db.rollback()
                logger.exception(
                    "invoice_alert_processing_failed",
                    invoice_id=str(invoice_id),
                    project=project_name,
                )
            invoices_checked += 1

        job_run.projects_checked = invoices_checked
        job_run.alerts_sent = alerts_sent
        await complete_job_run(db, job_run)

        logger.info(
            "job_completed",
            invoices_checked=invoices_checked,
            alerts_sent=alerts_sent,
        )
        return {
            "status": "completed",
            "job_run_id": job_run.id,
            "invoices_checked": invoices_checked,
            "alerts_sent": alerts_sent,
        }
    except Exception as e:
        logger.exception("job_failed")
        return await complete_with_error(db, job_run, str(e))
