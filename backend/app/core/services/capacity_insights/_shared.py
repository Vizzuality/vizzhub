"""Shared helpers for the capacity insights query family.

This subpackage hosts the analytical cross-module JOINs (core tables +
tracker tables) for the capacity views. The helpers here are reused by
``insights`` (overview), ``fa_detail``, ``user_detail`` and ``allocation``.
"""

import math
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.core.sql_helpers import format_user_display_name
from app.modules.tracker.models.reporting_period import ReportingPeriodDB


def _reportable_user_filter() -> list:
    """SQL filter clauses for the canonical reportable-user definition.

    A user is reportable when they are active and required to file
    project reports. The on-leave semantic (zero or full-absence reporting)
    is applied separately at the row level via ``_is_on_leave``.
    """
    return [
        UserDB.active.is_(True),
        UserDB.requires_project_reporting.is_(True),
    ]


def _is_on_leave(total_pct: float, absence_pct: float) -> bool:
    """A user is effectively on-leave for a period when they didn't report
    (total <= 0) or filed an essentially all-absence report (absence ~= 1.0).

    Under "absence ~= 1.0" we use ``math.isclose`` with ``abs_tol=1e-4`` so
    over/under-reporters whose absence equals their total also qualify (the
    practical case is ``total == absence == 1.0``)."""
    if total_pct <= 0:
        return True
    if math.isclose(absence_pct, 1.0, abs_tol=1e-4):
        return True
    return math.isclose(absence_pct, total_pct, abs_tol=1e-4)


TARGET_FA_MAPPING: dict[str, str] = {
    "Frontend Developer": "FE",
    "Backend Developer": "BE",
    "Designer": "Design",
    "Project Manager": "PM",
    "Scientist": "Sci",
    "Communications": "Coms",
}


SHORT_TO_FA_NAME: dict[str, str] = {v: k for k, v in TARGET_FA_MAPPING.items()}


def _format_user_name(
    first_name: str | None,
    last_name: str | None,
    full_name: str | None = None,
    email: str | None = None,
) -> str:
    """Format as 'F. Lastname' with fallbacks: first/last > full_name > email prefix."""
    if first_name and last_name:
        return f"{first_name[0]}. {last_name}"
    if last_name:
        return last_name
    if first_name:
        return first_name
    if full_name:
        parts = full_name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}. {parts[-1]}"
        return full_name
    if email:
        local = email.split("@")[0]
        parts = local.replace("_", ".").split(".")
        if len(parts) >= 2:
            return f"{parts[0][0].upper()}. {parts[-1].capitalize()}"
        return local.capitalize()
    return "Unknown"


def _format_full_name(
    first_name: str | None,
    last_name: str | None,
    full_name: str | None = None,
    email: str | None = None,
) -> str:
    """Format as 'Firstname Lastname' with the shared fallback chain."""
    return format_user_display_name(first_name, last_name, full_name, email)


async def _get_finished_periods(
    db: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
    default_limit: int = 3,
) -> list[tuple]:
    """Fetch reporting periods for allocation views, newest first.

    If start_date/end_date provided, includes finished and active periods
    in that range (so users see data for the period they selected).
    Otherwise returns the most recent ``default_limit`` finished periods.
    """
    if start_date and end_date:
        query = (
            select(ReportingPeriodDB.id, ReportingPeriodDB.date)
            .where(
                ReportingPeriodDB.status.in_(["finished", "active"]),
                ReportingPeriodDB.date >= start_date,
                ReportingPeriodDB.date <= end_date,
            )
            .order_by(ReportingPeriodDB.date.desc())
        )
    else:
        query = (
            select(ReportingPeriodDB.id, ReportingPeriodDB.date)
            .where(ReportingPeriodDB.status == "finished")
            .order_by(ReportingPeriodDB.date.desc())
            .limit(default_limit)
        )

    result = await db.execute(query)
    return list(result)
