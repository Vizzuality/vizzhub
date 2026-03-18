"""Project cost aggregation queries."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.user import UserDB
from app.modules.tracker.constants import DEFAULT_RATE
from app.modules.tracker.models.non_staff_cost import NonStaffCostDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.models.project_settings import TrackerProjectSettingsDB
from app.modules.tracker.schemas.project_cost import (
    PeriodCostBreakdown,
    ProjectCostSummary,
    ProjectCostSummaryLite,
    ProjectReportPartResponse,
)


async def get_project_cost_summary(
    db: AsyncSession,
    project_id: UUID,
) -> ProjectCostSummary:
    """Aggregate staff and non-staff costs for a project across all periods."""
    settings_result = await db.execute(
        select(TrackerProjectSettingsDB).where(
            TrackerProjectSettingsDB.project_id == project_id
        )
    )
    settings = settings_result.scalar_one_or_none()
    budget = float(settings.budget) if settings and settings.budget is not None else None
    contract_rate = float(settings.contract_rate) if settings else float(DEFAULT_RATE)

    # Staff costs grouped by period
    staff_query = (
        select(
            ReportingPeriodDB.id.label("period_id"),
            ReportingPeriodDB.date.label("period_date"),
            func.coalesce(func.sum(ReportPartDB.cost), 0).label("staff_cost"),
            func.count(ReportPartDB.id).label("parts_count"),
        )
        .select_from(ReportPartDB)
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .join(ReportingPeriodDB, ReportDB.reporting_period_id == ReportingPeriodDB.id)
        .where(ReportPartDB.project_id == project_id)
        .where(ReportDB.estimated.is_(False))
        .where(ReportPartDB.percentage.isnot(None))
        .where(ReportPartDB.percentage > 0)
        .group_by(ReportingPeriodDB.id, ReportingPeriodDB.date)
    )
    staff_result = await db.execute(staff_query)
    staff_rows = staff_result.all()

    # Non-staff costs grouped by period
    non_staff_query = (
        select(
            ReportingPeriodDB.id.label("period_id"),
            ReportingPeriodDB.date.label("period_date"),
            func.coalesce(func.sum(NonStaffCostDB.cost), 0).label("non_staff_cost"),
        )
        .select_from(NonStaffCostDB)
        .join(
            ReportingPeriodDB,
            NonStaffCostDB.reporting_period_id == ReportingPeriodDB.id,
        )
        .where(NonStaffCostDB.project_id == project_id)
        .group_by(ReportingPeriodDB.id, ReportingPeriodDB.date)
    )
    non_staff_result = await db.execute(non_staff_query)
    non_staff_rows = non_staff_result.all()

    # Merge periods from both queries
    period_map: dict[UUID, dict] = defaultdict(
        lambda: {
            "staff_cost": 0.0,
            "non_staff_cost": 0.0,
            "parts_count": 0,
            "date": None,
        }
    )

    for row in staff_rows:
        entry = period_map[row.period_id]
        entry["staff_cost"] = float(row.staff_cost)
        entry["parts_count"] = row.parts_count
        entry["date"] = row.period_date

    for row in non_staff_rows:
        entry = period_map[row.period_id]
        entry["non_staff_cost"] = float(row.non_staff_cost)
        entry["date"] = row.period_date

    periods = [
        PeriodCostBreakdown(
            period_id=pid,
            date=data["date"],
            staff_cost=data["staff_cost"],
            non_staff_cost=data["non_staff_cost"],
            total=data["staff_cost"] + data["non_staff_cost"],
            parts_count=data["parts_count"],
        )
        for pid, data in period_map.items()
    ]
    periods.sort(key=lambda p: p.date, reverse=True)

    total_staff = sum(p.staff_cost for p in periods)
    total_non_staff = sum(p.non_staff_cost for p in periods)
    total_cost = total_staff + total_non_staff
    burn_percentage = (total_cost / budget * 100) if budget else None

    return ProjectCostSummary(
        project_id=project_id,
        budget=budget,
        contract_rate=contract_rate,
        staff_cost=total_staff,
        non_staff_cost=total_non_staff,
        total_cost=total_cost,
        burn_percentage=burn_percentage,
        periods=periods,
    )


async def get_batch_cost_summaries(
    db: AsyncSession,
    project_ids: list[UUID],
) -> dict[UUID, ProjectCostSummaryLite]:
    """Batch cost summaries for multiple projects using 2 aggregate queries."""
    settings_result = await db.execute(
        select(TrackerProjectSettingsDB).where(
            TrackerProjectSettingsDB.project_id.in_(project_ids)
        )
    )
    settings_map = {s.project_id: s for s in settings_result.scalars().all()}

    staff_query = (
        select(
            ReportPartDB.project_id,
            func.coalesce(func.sum(ReportPartDB.cost), 0).label("staff_cost"),
        )
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .where(ReportPartDB.project_id.in_(project_ids))
        .where(ReportDB.estimated.is_(False))
        .where(ReportPartDB.percentage.isnot(None))
        .where(ReportPartDB.percentage > 0)
        .group_by(ReportPartDB.project_id)
    )
    staff_result = await db.execute(staff_query)
    staff_map = {row.project_id: float(row.staff_cost) for row in staff_result.all()}

    non_staff_query = (
        select(
            NonStaffCostDB.project_id,
            func.coalesce(func.sum(NonStaffCostDB.cost), 0).label("non_staff_cost"),
        )
        .where(NonStaffCostDB.project_id.in_(project_ids))
        .group_by(NonStaffCostDB.project_id)
    )
    non_staff_result = await db.execute(non_staff_query)
    non_staff_map = {
        row.project_id: float(row.non_staff_cost) for row in non_staff_result.all()
    }

    results: dict[UUID, ProjectCostSummaryLite] = {}
    for pid in project_ids:
        settings = settings_map.get(pid)
        budget = float(settings.budget) if settings and settings.budget else None
        staff = staff_map.get(pid, 0.0)
        non_staff = non_staff_map.get(pid, 0.0)
        total = round(staff + non_staff, 2)
        burn = round(total / budget * 100, 2) if budget else None

        results[pid] = ProjectCostSummaryLite(
            budget=budget,
            total_cost=total,
            staff_cost=round(staff, 2),
            non_staff_cost=round(non_staff, 2),
            burn_percentage=burn,
        )

    return results


async def get_project_report_parts(
    db: AsyncSession,
    project_id: UUID,
    period_id: UUID | None = None,
) -> list[ProjectReportPartResponse]:
    """List report parts for a project with user and functional area details."""
    query = (
        select(
            ReportPartDB.id,
            ReportingPeriodDB.date.label("period_date"),
            UserDB.name.label("user_name"),
            UserDB.email.label("user_email"),
            FunctionalAreaDB.name.label("functional_area"),
            ReportPartDB.percentage,
            ReportPartDB.days,
            ReportPartDB.cost,
            ReportDB.estimated,
        )
        .select_from(ReportPartDB)
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .join(ReportingPeriodDB, ReportDB.reporting_period_id == ReportingPeriodDB.id)
        .join(UserDB, ReportDB.user_id == UserDB.id)
        .outerjoin(
            FunctionalAreaDB,
            ReportPartDB.functional_area_id == FunctionalAreaDB.id,
        )
        .where(ReportPartDB.project_id == project_id)
        .where(ReportPartDB.percentage.isnot(None))
        .where(ReportPartDB.percentage > 0)
        .order_by(ReportingPeriodDB.date.desc(), UserDB.name.asc())
    )

    if period_id is not None:
        query = query.where(ReportDB.reporting_period_id == period_id)

    result = await db.execute(query)
    rows = result.all()

    return [
        ProjectReportPartResponse(
            id=row.id,
            period_date=row.period_date,
            user_name=row.user_name,
            user_email=row.user_email,
            functional_area=row.functional_area,
            percentage=float(row.percentage) if row.percentage is not None else None,
            days=float(row.days) if row.days is not None else None,
            cost=float(row.cost) if row.cost is not None else None,
            estimated=row.estimated,
        )
        for row in rows
    ]
