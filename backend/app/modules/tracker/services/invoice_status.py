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
    """Latest ``postponed_to`` + count per invoice."""
    return (
        select(
            InvoicePostponementDB.invoice_id,
            func.max(InvoicePostponementDB.postponed_to).label("postponed_to"),
            func.count().label("postpone_count"),
        )
        .group_by(InvoicePostponementDB.invoice_id)
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
