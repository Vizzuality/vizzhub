"""Shared invoice effective-status SQL helpers.

Same expressions used by both user (`tracker/api/invoices.py`) and admin
(`tracker/api/admin_invoices.py`) endpoints — keep them here so a change
to the postponement contract (e.g. the 30-day window) lands once, not
twice.
"""

from sqlalchemy import case, func, literal, select

from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB


def postponement_subquery():
    """Most-recent ``postponed_to`` (by ``created_at``) + count per invoice.

    Picks the postponement row with the latest ``created_at`` per invoice
    rather than the maximum ``postponed_to`` date, so a corrective
    postponement closer in time supersedes an earlier far-future one
    (audit finding #27).
    """
    ranked = (
        select(
            InvoicePostponementDB.invoice_id,
            InvoicePostponementDB.postponed_to,
            func.row_number()
            .over(
                partition_by=InvoicePostponementDB.invoice_id,
                order_by=InvoicePostponementDB.created_at.desc(),
            )
            .label("rn"),
            func.count()
            .over(partition_by=InvoicePostponementDB.invoice_id)
            .label("postpone_count"),
        )
        .subquery()
    )
    return (
        select(
            ranked.c.invoice_id,
            ranked.c.postponed_to,
            ranked.c.postpone_count,
        )
        .where(ranked.c.rn == 1)
        .subquery()
    )


def effective_status_expr(today, pp_sub):
    """SQL CASE expression resolving the displayed status for an invoice.

    - ``postponed`` when an active postponement (`postponed_to > today`) exists.
    - ``pending_to_issue`` when the postponement expired *or* the original
      schedule is past due.
    - Otherwise: the stored status.
    """
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
