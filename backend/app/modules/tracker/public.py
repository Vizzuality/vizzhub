"""Public interface for the tracker module.

Other modules should import from here, never from tracker internals.
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracker.models.non_staff_cost import NonStaffCostDB
from app.modules.tracker.models.progress_report import ProgressReportDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB


class TrackerEVMData(BaseModel):
    """EVM fields derived from tracker data for scorecard consumption."""

    cost_to_date: float | None = None
    percent_completed: float | None = None
    percent_planned: float | None = None


async def get_evm_from_tracker(
    project_id: UUID,
    db: AsyncSession,
    start_date: date | None = None,
    end_date: date | None = None,
) -> TrackerEVMData:
    """Compute EVM fields from tracker data for a project.

    - cost_to_date: total staff + non-staff costs
    - percent_completed: latest progress report percentage (0-1)
    - percent_planned: linear interpolation of project timeline (0-1)
    """
    cost = await _get_total_cost(project_id, db)
    progress = await _get_latest_progress(project_id, db)
    planned = _calculate_expected_progress(start_date, end_date)

    return TrackerEVMData(
        cost_to_date=cost,
        percent_completed=progress,
        percent_planned=planned,
    )


async def _get_total_cost(project_id: UUID, db: AsyncSession) -> float | None:
    """Sum of staff + non-staff costs across all periods."""
    staff_result = await db.execute(
        select(func.coalesce(func.sum(ReportPartDB.cost), 0))
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .where(
            ReportPartDB.project_id == project_id,
            ReportDB.estimated.is_(False),
            ReportPartDB.percentage.isnot(None),
            ReportPartDB.percentage > 0,
        )
    )
    staff = float(staff_result.scalar_one())

    non_staff_result = await db.execute(
        select(func.coalesce(func.sum(NonStaffCostDB.cost), 0)).where(
            NonStaffCostDB.project_id == project_id
        )
    )
    non_staff = float(non_staff_result.scalar_one())

    total = round(staff + non_staff, 2)
    return total if total > 0 else None


async def _get_latest_progress(project_id: UUID, db: AsyncSession) -> float | None:
    """Get the latest progress report percentage (0-1) for a project."""
    result = await db.execute(
        select(ProgressReportDB.percentage)
        .join(ReportingPeriodDB)
        .where(ProgressReportDB.project_id == project_id)
        .order_by(ReportingPeriodDB.date.desc())
        .limit(1)
    )
    pct = result.scalar_one_or_none()
    return float(pct) if pct is not None else None


def _calculate_expected_progress(
    start_date: date | None,
    end_date: date | None,
) -> float | None:
    """Linear interpolation of project timeline: (today - start) / (end - start)."""
    if not start_date or not end_date:
        return None

    total_days = (end_date - start_date).days
    if total_days <= 0:
        return None

    elapsed = (date.today() - start_date).days
    return max(0.0, min(1.0, elapsed / total_days))


async def inject_evm_into_preserved(
    preserved: dict,
    project_id: UUID,
    db: AsyncSession,
    budget: float | None,
    start_date: date | None,
    end_date: date | None,
) -> None:
    """Inject budget_total and tracker EVM fields into a preserved-fields dict."""
    if budget is not None:
        preserved["budget_total"] = budget
    tracker_evm = await get_evm_from_tracker(project_id, db, start_date, end_date)
    for field in ("cost_to_date", "percent_completed", "percent_planned"):
        value = getattr(tracker_evm, field)
        if value is not None:
            preserved[field] = value


def _logged_time_filter() -> ColumnElement[bool]:
    # Prepopulated parts nobody filled in carry no time; they must not pin a project.
    return ReportPartDB.percentage.isnot(None) & (ReportPartDB.percentage > 0)


async def has_tracker_references(project_id: UUID, db: AsyncSession) -> list[str]:
    """Check if a project has tracker references that block deletion.

    Returns a list of human-readable reference descriptions.
    """
    references: list[str] = []

    rp_count = (
        await db.execute(
            select(func.count())
            .select_from(ReportPartDB)
            .where(ReportPartDB.project_id == project_id, _logged_time_filter())
        )
    ).scalar() or 0
    if rp_count > 0:
        noun = "entry" if rp_count == 1 else "entries"
        references.append(f"Cannot delete: project has {rp_count} time report {noun}.")

    pr_count = (
        await db.execute(
            select(func.count())
            .select_from(ProgressReportDB)
            .where(ProgressReportDB.project_id == project_id)
        )
    ).scalar() or 0
    if pr_count > 0:
        noun = "report" if pr_count == 1 else "reports"
        references.append(f"Cannot delete: project has {pr_count} progress {noun}.")

    return references


async def delete_empty_report_parts(project_id: UUID, db: AsyncSession) -> int:
    """Remove a project's report parts that log no time, so the project can be deleted."""
    result = await db.execute(
        delete(ReportPartDB).where(ReportPartDB.project_id == project_id, ~_logged_time_filter())
    )
    return result.rowcount or 0
