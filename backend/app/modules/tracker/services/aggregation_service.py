"""Project cost aggregation queries."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.constants import DEFAULT_RATE
from app.modules.tracker.models.invoice import InvoiceDB
from app.modules.tracker.models.non_staff_cost import NonStaffCostDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.models.project_settings import TrackerProjectSettingsDB
from app.modules.tracker.schemas.aggregation import (
    AggregationPeriod,
    AggregationResponse,
    AggregationRow,
)
from app.modules.tracker.schemas.project_cost import (
    PeriodCostBreakdown,
    ProjectCostSummary,
    ProjectCostSummaryLite,
    ProjectReportPartResponse,
)


def _valid_parts_filter(query):
    """Apply standard filters: exclude estimated reports, null/zero percentage."""
    return (
        query
        .where(ReportDB.estimated.is_(False))
        .where(ReportPartDB.percentage.isnot(None))
        .where(ReportPartDB.percentage > 0)
    )


def _compute_burn_percentage(total_cost: float, budget: float | None) -> float | None:
    """Compute burn% using a single rounding policy across endpoints.

    Round total_cost to 2dp BEFORE dividing so single and batch endpoints
    agree to the cent. Returns None when budget is missing OR zero — the
    "null when zero" rule is intentional, not a fallthrough on truthy.
    """
    if budget is None or budget == 0:
        return None
    return round(round(total_cost, 2) / budget * 100, 2)


def _normalize_currency(currency: str | None) -> str | None:
    """Surface project.currency on cost summaries; do not fabricate when missing."""
    if currency is None:
        return None
    stripped = currency.strip()
    return stripped or None


async def get_project_cost_summary(
    db: AsyncSession,
    project_id: UUID,
) -> ProjectCostSummary:
    """Aggregate staff and non-staff costs for a project across all periods."""
    project = await db.get(ProjectDB, project_id)
    budget = float(project.budget) if project and project.budget is not None else None
    currency = _normalize_currency(project.currency) if project else None

    settings_result = await db.execute(
        select(TrackerProjectSettingsDB).where(
            TrackerProjectSettingsDB.project_id == project_id
        )
    )
    settings = settings_result.scalar_one_or_none()
    contract_rate = float(settings.contract_rate) if settings else float(DEFAULT_RATE)

    # Staff costs grouped by period
    staff_query = _valid_parts_filter(
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
    ).group_by(ReportingPeriodDB.id, ReportingPeriodDB.date)
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
    burn_percentage = _compute_burn_percentage(total_cost, budget)

    return ProjectCostSummary(
        project_id=project_id,
        budget=budget,
        contract_rate=contract_rate,
        staff_cost=total_staff,
        non_staff_cost=total_non_staff,
        total_cost=total_cost,
        burn_percentage=burn_percentage,
        currency=currency,
        periods=periods,
    )


async def get_batch_cost_summaries(
    db: AsyncSession,
    project_ids: list[UUID],
) -> dict[UUID, ProjectCostSummaryLite]:
    """Batch cost summaries for multiple projects using 2 aggregate queries."""
    projects_result = await db.execute(
        select(ProjectDB.id, ProjectDB.budget, ProjectDB.currency)
        .where(ProjectDB.id.in_(project_ids))
    )
    budget_map: dict[UUID, float] = {}
    currency_map: dict[UUID, str | None] = {}
    for row in projects_result.all():
        if row.budget is not None:
            budget_map[row.id] = float(row.budget)
        currency_map[row.id] = _normalize_currency(row.currency)

    staff_query = _valid_parts_filter(
        select(
            ReportPartDB.project_id,
            func.coalesce(func.sum(ReportPartDB.cost), 0).label("staff_cost"),
        )
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .where(ReportPartDB.project_id.in_(project_ids))
    ).group_by(ReportPartDB.project_id)
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

    income_query = (
        select(
            InvoiceDB.project_id,
            func.coalesce(func.sum(InvoiceDB.amount), 0).label("income"),
        )
        .where(
            InvoiceDB.project_id.in_(project_ids),
            InvoiceDB.status == "paid",
        )
        .group_by(InvoiceDB.project_id)
    )
    income_result = await db.execute(income_query)
    income_map = {row.project_id: float(row.income) for row in income_result.all()}

    results: dict[UUID, ProjectCostSummaryLite] = {}
    for pid in project_ids:
        budget = budget_map.get(pid)
        staff = staff_map.get(pid, 0.0)
        non_staff = non_staff_map.get(pid, 0.0)
        total = round(staff + non_staff, 2)
        burn = _compute_burn_percentage(total, budget)

        results[pid] = ProjectCostSummaryLite(
            budget=budget,
            total_cost=total,
            staff_cost=round(staff, 2),
            non_staff_cost=round(non_staff, 2),
            burn_percentage=burn,
            income=round(income_map.get(pid, 0.0), 2),
            currency=currency_map.get(pid),
        )

    return results


async def get_project_report_parts(
    db: AsyncSession,
    project_id: UUID,
    period_id: UUID | None = None,
) -> list[ProjectReportPartResponse]:
    """List report parts for a project with user and functional area details.

    Includes estimated reports (shown with badge in UI), unlike aggregation
    functions which exclude them via _valid_parts_filter.
    """
    base_query = (
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
        base_query = base_query.where(ReportDB.reporting_period_id == period_id)

    result = await db.execute(base_query)
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


from app.modules.tracker.constants import ALLOWED_GROUP_BY  # noqa: E402,F401


async def _aggregate_fa_user(
    db: AsyncSession,
    project_id: UUID,
) -> AggregationResponse:
    """Aggregate report_parts by functional_area with per-user children."""
    query = _valid_parts_filter(
        select(
            FunctionalAreaDB.name.label("fa_name"),
            UserDB.name.label("user_name"),
            UserDB.email.label("user_email"),
            ReportingPeriodDB.date.label("period_date"),
            func.coalesce(func.sum(ReportPartDB.days), 0).label("days"),
            func.coalesce(func.sum(ReportPartDB.cost), 0).label("cost"),
        )
        .select_from(ReportPartDB)
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .join(ReportingPeriodDB, ReportDB.reporting_period_id == ReportingPeriodDB.id)
        .join(FunctionalAreaDB, ReportPartDB.functional_area_id == FunctionalAreaDB.id)
        .join(UserDB, ReportDB.user_id == UserDB.id)
        .where(ReportPartDB.project_id == project_id)
    ).group_by(
        "fa_name", "user_name", "user_email", ReportingPeriodDB.date,
    ).order_by("fa_name", "user_name", ReportingPeriodDB.date)

    result = await db.execute(query)
    raw_rows = result.all()

    fa_map: dict[str, dict] = {}
    for row in raw_rows:
        fa_key = row.fa_name or "Unknown"
        if fa_key not in fa_map:
            fa_map[fa_key] = {
                "total_days": 0.0,
                "total_cost": 0.0,
                "periods_map": defaultdict(lambda: {"days": 0.0, "cost": 0.0}),
                "users": {},
            }
        fa = fa_map[fa_key]
        days = float(row.days)
        cost = float(row.cost)
        fa["total_days"] += days
        fa["total_cost"] += cost
        period_date = row.period_date
        fa["periods_map"][period_date]["days"] += days
        fa["periods_map"][period_date]["cost"] += cost

        user_key = row.user_email or row.user_name or "Unknown"
        if user_key not in fa["users"]:
            fa["users"][user_key] = {
                "name": row.user_name or "Unknown",
                "email": row.user_email,
                "total_days": 0.0,
                "total_cost": 0.0,
                "periods": [],
            }
        user = fa["users"][user_key]
        user["total_days"] += days
        user["total_cost"] += cost
        user["periods"].append(AggregationPeriod(date=period_date, days=days, cost=cost))

    rows = []
    for fa_name, fa in fa_map.items():
        children = [
            AggregationRow(
                name=u["name"],
                email=u["email"],
                total_days=round(u["total_days"], 2),
                total_cost=round(u["total_cost"], 2),
                periods=u["periods"],
            )
            for u in fa["users"].values()
        ]
        children.sort(key=lambda r: r.total_days, reverse=True)
        periods = [
            AggregationPeriod(date=d, days=round(v["days"], 2), cost=round(v["cost"], 2))
            for d, v in sorted(fa["periods_map"].items())
        ]
        rows.append(
            AggregationRow(
                name=fa_name,
                total_days=round(fa["total_days"], 2),
                total_cost=round(fa["total_cost"], 2),
                periods=periods,
                children=children,
            )
        )
    rows.sort(key=lambda r: r.total_days, reverse=True)
    return AggregationResponse(group_by="functional_area_user", rows=rows)


async def get_project_aggregations(
    db: AsyncSession,
    project_id: UUID,
    group_by: str,
) -> AggregationResponse:
    """Aggregate report_parts by functional_area or user."""
    if group_by == "functional_area_user":
        return await _aggregate_fa_user(db, project_id)

    if group_by == "functional_area":
        name_col = FunctionalAreaDB.name.label("name")
        email_col = func.cast(None, UserDB.email.type).label("email")
        join_clause = ReportPartDB.functional_area_id == FunctionalAreaDB.id
        join_target = FunctionalAreaDB
    else:
        name_col = UserDB.name.label("name")
        email_col = UserDB.email.label("email")
        join_clause = ReportDB.user_id == UserDB.id
        join_target = UserDB

    query = _valid_parts_filter(
        select(
            name_col,
            email_col,
            ReportingPeriodDB.date.label("period_date"),
            func.coalesce(func.sum(ReportPartDB.days), 0).label("days"),
            func.coalesce(func.sum(ReportPartDB.cost), 0).label("cost"),
        )
        .select_from(ReportPartDB)
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .join(ReportingPeriodDB, ReportDB.reporting_period_id == ReportingPeriodDB.id)
        .join(join_target, join_clause)
        .where(ReportPartDB.project_id == project_id)
    ).group_by("name", "email", ReportingPeriodDB.date).order_by("name", ReportingPeriodDB.date)

    result = await db.execute(query)
    raw_rows = result.all()

    row_map: dict[str, dict] = {}
    for row in raw_rows:
        key = row.name or "Unknown"
        if key not in row_map:
            row_map[key] = {
                "name": key,
                "email": row.email,
                "total_days": 0.0,
                "total_cost": 0.0,
                "periods": [],
            }
        entry = row_map[key]
        days = float(row.days)
        cost = float(row.cost)
        entry["total_days"] += days
        entry["total_cost"] += cost
        entry["periods"].append(
            AggregationPeriod(date=row.period_date, days=days, cost=cost)
        )

    rows = [
        AggregationRow(
            name=v["name"],
            email=v["email"],
            total_days=round(v["total_days"], 2),
            total_cost=round(v["total_cost"], 2),
            periods=v["periods"],
        )
        for v in row_map.values()
    ]
    rows.sort(key=lambda r: r.total_days, reverse=True)

    return AggregationResponse(group_by=group_by, rows=rows)
