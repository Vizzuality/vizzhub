"""Shared invoice effective-status SQL helpers.

Same expressions used by both user (`tracker/api/invoices.py`) and admin
(`tracker/api/admin_invoices.py`) endpoints — keep them here so a change
to the postponement contract (e.g. the 30-day window, approval workflow)
lands once, not at every callsite.

Two subqueries summarize the postponement history per invoice:

- ``latest_postponement_subquery`` — latest row regardless of approval
  state, used to detect ``postpone_pending`` (in-flight request).
- ``approved_postponement_subquery`` — latest approved row + count of
  approved rows, used to compute the currently-effective postponed date.
"""

from sqlalchemy import case, func, literal, select

from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.postponement import InvoicePostponementDB


def latest_postponement_subquery():
    """Per-invoice: latest postponement row (any approval state)."""
    ranked = select(
        InvoicePostponementDB.invoice_id,
        InvoicePostponementDB.postponed_to,
        InvoicePostponementDB.approval_status,
        func.row_number()
        .over(
            partition_by=InvoicePostponementDB.invoice_id,
            order_by=InvoicePostponementDB.created_at.desc(),
        )
        .label("rn"),
    ).subquery()
    return (
        select(
            ranked.c.invoice_id,
            ranked.c.postponed_to.label("latest_postponed_to"),
            ranked.c.approval_status.label("latest_status"),
        )
        .where(ranked.c.rn == 1)
        .subquery()
    )


def approved_postponement_subquery():
    """Per-invoice: latest *approved* postponement row + count of approvals.

    Picks the most recently created approved row (not the furthest-future
    ``postponed_to``) so a corrective postponement supersedes an earlier
    far-future one — same semantics as before the approval workflow.
    """
    approved = (
        select(InvoicePostponementDB)
        .where(InvoicePostponementDB.approval_status == "approved")
        .subquery()
    )
    ranked = select(
        approved.c.invoice_id,
        approved.c.postponed_to,
        func.row_number()
        .over(
            partition_by=approved.c.invoice_id,
            order_by=approved.c.created_at.desc(),
        )
        .label("rn"),
        func.count().over(partition_by=approved.c.invoice_id).label("approved_count"),
    ).subquery()
    return (
        select(
            ranked.c.invoice_id,
            ranked.c.postponed_to.label("approved_postponed_to"),
            ranked.c.approved_count,
        )
        .where(ranked.c.rn == 1)
        .subquery()
    )


# Backwards-compatible alias used by older import sites.
postponement_subquery = approved_postponement_subquery


def effective_status_expr(today, latest_pp, approved_pp):
    """SQL CASE expression resolving the displayed status for an invoice.

    Resolution order:

    1. ``postpone_pending`` — most recent postponement is a pending request
    2. ``postponed`` — latest approved postponement is in the future
    3. ``pending_to_issue`` — latest approved postponement is in the past,
       OR original ``scheduled`` row whose ``due_date`` is past
    4. otherwise the raw ``InvoiceDB.status``
    """
    return case(
        (
            latest_pp.c.latest_status == "pending",
            literal("postpone_pending"),
        ),
        (
            InvoiceDB.status.in_(["scheduled", "pending_to_issue"])
            & approved_pp.c.approved_postponed_to.isnot(None)
            & (approved_pp.c.approved_postponed_to > today),
            literal("postponed"),
        ),
        (
            InvoiceDB.status.in_(["scheduled", "pending_to_issue"])
            & approved_pp.c.approved_postponed_to.isnot(None)
            & (approved_pp.c.approved_postponed_to <= today),
            literal("pending_to_issue"),
        ),
        (
            (InvoiceDB.status == "scheduled") & (InvoiceDB.due_date <= today),
            literal("pending_to_issue"),
        ),
        else_=InvoiceDB.status,
    )
