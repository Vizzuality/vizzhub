"""Tracker data access — projects, costs, time, invoices, progress, periods, jira."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models import (
    BudgetLineDB,
    InvoiceDB,
    NonStaffCostDB,
    ProgressReportDB,
    ReportDB,
    ReportPartDB,
    ReportingPeriodDB,
    TrackerProjectSettingsDB,
)
from app.modules.tracker.models.postponement import InvoicePostponementDB


def _user_full_name():
    """SQL expression: first + last, falling back to name, then email prefix."""
    return case(
        (
            UserDB.first_name.isnot(None),
            func.concat(UserDB.first_name, literal(" "), func.coalesce(UserDB.last_name, literal(""))),
        ),
        else_=func.coalesce(UserDB.name, func.split_part(UserDB.email, literal("@"), 1)),
    )


def _valid_parts_filter(query):
    """Exclude estimated reports and null/zero percentage parts."""
    return (
        query
        .where(ReportDB.estimated.is_(False))
        .where(ReportPartDB.percentage.isnot(None))
        .where(ReportPartDB.percentage > 0)
    )


def _to_float(val: Decimal | None) -> float | None:
    return float(val) if val is not None else None


# ---------------------------------------------------------------------------
# 1. tracker_get_projects
# ---------------------------------------------------------------------------

async def get_projects(
    session: AsyncSession,
    status: str | None = None,
    is_billable: bool | None = None,
) -> list[dict]:
    """List projects with cost summary (budget, burn, staff/non-staff, income)."""
    pm_name = _user_full_name().label("project_manager_name")
    pm_user = UserDB.__table__.alias("pm_user")
    pm_name_expr = case(
        (
            pm_user.c.first_name.isnot(None),
            func.concat(pm_user.c.first_name, literal(" "), func.coalesce(pm_user.c.last_name, literal(""))),
        ),
        else_=func.coalesce(pm_user.c.name, func.split_part(pm_user.c.email, literal("@"), 1)),
    ).label("project_manager_name")

    stmt = (
        select(
            ProjectDB.id,
            ProjectDB.name,
            ProjectDB.code,
            ProjectDB.status,
            ProjectDB.is_billable,
            ProjectDB.currency,
            ProjectDB.budget,
            ProjectDB.start_date,
            ProjectDB.end_date,
            pm_name_expr,
        )
        .outerjoin(pm_user, ProjectDB.project_manager_id == pm_user.c.id)
        .where(ProjectDB.is_absence.is_(False))
        .order_by(ProjectDB.name)
    )

    if status is not None:
        stmt = stmt.where(ProjectDB.status == status)
    if is_billable is not None:
        stmt = stmt.where(ProjectDB.is_billable == is_billable)

    result = await session.execute(stmt)
    projects = result.all()
    if not projects:
        return []

    project_ids = [p.id for p in projects]

    # Batch cost queries
    staff_result = await session.execute(
        _valid_parts_filter(
            select(
                ReportPartDB.project_id,
                func.coalesce(func.sum(ReportPartDB.cost), 0).label("staff_cost"),
            )
            .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
            .where(ReportPartDB.project_id.in_(project_ids))
        ).group_by(ReportPartDB.project_id)
    )
    staff_map = {r.project_id: float(r.staff_cost) for r in staff_result.all()}

    non_staff_result = await session.execute(
        select(
            NonStaffCostDB.project_id,
            func.coalesce(func.sum(NonStaffCostDB.cost), 0).label("non_staff_cost"),
        )
        .where(NonStaffCostDB.project_id.in_(project_ids))
        .group_by(NonStaffCostDB.project_id)
    )
    non_staff_map = {r.project_id: float(r.non_staff_cost) for r in non_staff_result.all()}

    income_result = await session.execute(
        select(
            InvoiceDB.project_id,
            func.coalesce(func.sum(InvoiceDB.amount), 0).label("income"),
        )
        .where(InvoiceDB.project_id.in_(project_ids), InvoiceDB.status == "paid")
        .group_by(InvoiceDB.project_id)
    )
    income_map = {r.project_id: float(r.income) for r in income_result.all()}

    rows = []
    for p in projects:
        budget = _to_float(p.budget)
        staff = staff_map.get(p.id, 0.0)
        non_staff = non_staff_map.get(p.id, 0.0)
        total = round(staff + non_staff, 2)
        burn = round(total / budget * 100, 2) if budget else None

        rows.append({
            "id": str(p.id),
            "name": p.name,
            "code": p.code,
            "status": p.status,
            "is_billable": p.is_billable,
            "currency": p.currency,
            "budget": budget,
            "start_date": p.start_date,
            "end_date": p.end_date,
            "project_manager": p.project_manager_name,
            "staff_cost": round(staff, 2),
            "non_staff_cost": round(non_staff, 2),
            "total_cost": total,
            "burn_percentage": burn,
            "income": round(income_map.get(p.id, 0.0), 2),
        })

    return rows


# ---------------------------------------------------------------------------
# 2. tracker_get_project_detail
# ---------------------------------------------------------------------------

async def get_project_detail(
    session: AsyncSession,
    project_id: UUID,
) -> dict | None:
    """Full project detail: info, budget lines, cost summary by period."""
    project = await session.get(ProjectDB, project_id)
    if project is None:
        return None

    # Budget lines
    bl_result = await session.execute(
        select(
            BudgetLineDB.id,
            BudgetLineDB.days,
            BudgetLineDB.percentage,
            BudgetLineDB.details,
            FunctionalAreaDB.name.label("functional_area"),
        )
        .outerjoin(FunctionalAreaDB, BudgetLineDB.functional_area_id == FunctionalAreaDB.id)
        .where(BudgetLineDB.project_id == project_id)
        .order_by(FunctionalAreaDB.name)
    )
    budget_lines = [
        {
            "id": str(r.id),
            "functional_area": r.functional_area,
            "days": _to_float(r.days),
            "percentage": _to_float(r.percentage),
            "details": r.details,
        }
        for r in bl_result.all()
    ]

    # Contract rate
    settings_result = await session.execute(
        select(TrackerProjectSettingsDB.contract_rate)
        .where(TrackerProjectSettingsDB.project_id == project_id)
    )
    contract_rate = settings_result.scalar_one_or_none()
    contract_rate = _to_float(contract_rate) or 175.0

    # Staff costs by period
    staff_result = await session.execute(
        _valid_parts_filter(
            select(
                ReportingPeriodDB.date.label("period_date"),
                func.coalesce(func.sum(ReportPartDB.cost), 0).label("staff_cost"),
            )
            .select_from(ReportPartDB)
            .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
            .join(ReportingPeriodDB, ReportDB.reporting_period_id == ReportingPeriodDB.id)
            .where(ReportPartDB.project_id == project_id)
        ).group_by(ReportingPeriodDB.date)
    )
    staff_by_period = {r.period_date: float(r.staff_cost) for r in staff_result.all()}

    # Non-staff costs by period
    ns_result = await session.execute(
        select(
            ReportingPeriodDB.date.label("period_date"),
            func.coalesce(func.sum(NonStaffCostDB.cost), 0).label("non_staff_cost"),
        )
        .select_from(NonStaffCostDB)
        .join(ReportingPeriodDB, NonStaffCostDB.reporting_period_id == ReportingPeriodDB.id)
        .where(NonStaffCostDB.project_id == project_id)
        .group_by(ReportingPeriodDB.date)
    )
    ns_by_period = {r.period_date: float(r.non_staff_cost) for r in ns_result.all()}

    all_dates = sorted(set(staff_by_period) | set(ns_by_period), reverse=True)
    periods = []
    total_staff = 0.0
    total_non_staff = 0.0
    for d in all_dates:
        s = staff_by_period.get(d, 0.0)
        ns = ns_by_period.get(d, 0.0)
        total_staff += s
        total_non_staff += ns
        periods.append({
            "date": d,
            "staff_cost": round(s, 2),
            "non_staff_cost": round(ns, 2),
            "total": round(s + ns, 2),
        })

    budget = _to_float(project.budget)
    total_cost = round(total_staff + total_non_staff, 2)

    # PM name
    pm_name = None
    if project.project_manager_id:
        pm_result = await session.execute(
            select(UserDB).where(UserDB.id == project.project_manager_id)
        )
        pm = pm_result.scalar_one_or_none()
        if pm:
            pm_name = (
                f"{pm.first_name} {pm.last_name}".strip()
                if pm.first_name
                else pm.name or pm.email.split("@")[0]
            )

    return {
        "id": str(project.id),
        "name": project.name,
        "code": project.code,
        "status": project.status,
        "is_billable": project.is_billable,
        "currency": project.currency,
        "budget": budget,
        "contract_rate": contract_rate,
        "start_date": project.start_date,
        "end_date": project.end_date,
        "project_manager": pm_name,
        "summary": project.summary,
        "budget_lines": budget_lines,
        "cost_summary": {
            "staff_cost": round(total_staff, 2),
            "non_staff_cost": round(total_non_staff, 2),
            "total_cost": total_cost,
            "burn_percentage": round(total_cost / budget * 100, 2) if budget else None,
            "periods": periods,
        },
    }


# ---------------------------------------------------------------------------
# 3. tracker_get_project_time
# ---------------------------------------------------------------------------

async def get_project_time(
    session: AsyncSession,
    project_id: UUID,
    group_by: str = "user",
) -> list[dict]:
    """Time allocation for a project grouped by user or functional_area.

    Returns aggregated days/cost per group with per-period breakdown.
    """
    if group_by == "functional_area":
        name_col = FunctionalAreaDB.name.label("group_name")
        join_target = FunctionalAreaDB
        join_clause = ReportPartDB.functional_area_id == FunctionalAreaDB.id
    else:
        name_col = _user_full_name().label("group_name")
        join_target = UserDB
        join_clause = ReportDB.user_id == UserDB.id

    query = _valid_parts_filter(
        select(
            name_col,
            ReportingPeriodDB.date.label("period_date"),
            func.coalesce(func.sum(ReportPartDB.days), 0).label("days"),
            func.coalesce(func.sum(ReportPartDB.cost), 0).label("cost"),
        )
        .select_from(ReportPartDB)
        .join(ReportDB, ReportPartDB.report_id == ReportDB.id)
        .join(ReportingPeriodDB, ReportDB.reporting_period_id == ReportingPeriodDB.id)
        .join(join_target, join_clause)
        .where(ReportPartDB.project_id == project_id)
    ).group_by("group_name", ReportingPeriodDB.date).order_by("group_name", ReportingPeriodDB.date)

    result = await session.execute(query)

    group_map: dict[str, dict] = {}
    for row in result.all():
        key = row.group_name or "Unknown"
        if key not in group_map:
            group_map[key] = {"total_days": 0.0, "total_cost": 0.0, "periods": []}
        entry = group_map[key]
        days = float(row.days)
        cost = float(row.cost)
        entry["total_days"] += days
        entry["total_cost"] += cost
        entry["periods"].append({"date": row.period_date, "days": round(days, 2), "cost": round(cost, 2)})

    rows = [
        {
            "name": name,
            "total_days": round(data["total_days"], 2),
            "total_cost": round(data["total_cost"], 2),
            "periods": data["periods"],
        }
        for name, data in group_map.items()
    ]
    rows.sort(key=lambda r: r["total_days"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 4. tracker_get_project_invoices
# ---------------------------------------------------------------------------

async def get_project_invoices(
    session: AsyncSession,
    project_id: UUID,
) -> list[dict]:
    """Invoices for a project with effective status (includes postponed)."""
    today = date.today()

    # Active postponement subquery: latest postponement still in the future
    latest_postponement = (
        select(
            InvoicePostponementDB.invoice_id,
            func.max(InvoicePostponementDB.postponed_to).label("postponed_to"),
            func.count(InvoicePostponementDB.id).label("postpone_count"),
        )
        .group_by(InvoicePostponementDB.invoice_id)
        .subquery()
    )

    stmt = (
        select(
            InvoiceDB.id,
            InvoiceDB.code,
            InvoiceDB.amount,
            InvoiceDB.due_date,
            InvoiceDB.invoiced_on,
            InvoiceDB.milestone,
            InvoiceDB.observations,
            InvoiceDB.status,
            latest_postponement.c.postponed_to,
            func.coalesce(latest_postponement.c.postpone_count, 0).label("postpone_count"),
        )
        .outerjoin(latest_postponement, InvoiceDB.id == latest_postponement.c.invoice_id)
        .where(InvoiceDB.project_id == project_id)
        .order_by(InvoiceDB.due_date)
    )

    result = await session.execute(stmt)
    rows = []
    for r in result.all():
        # Compute effective status
        effective_status = r.status
        if r.status != "paid" and r.postponed_to and r.postponed_to > today:
            effective_status = "postponed"
        elif r.status == "scheduled" and r.due_date <= today:
            effective_status = "pending_to_issue"

        rows.append({
            "id": str(r.id),
            "code": r.code,
            "amount": _to_float(r.amount),
            "due_date": r.due_date,
            "invoiced_on": r.invoiced_on,
            "milestone": r.milestone,
            "observations": r.observations,
            "status": effective_status,
            "stored_status": r.status,
            "postpone_count": r.postpone_count,
            "postponed_to": r.postponed_to,
        })

    return rows


# ---------------------------------------------------------------------------
# 5. tracker_get_project_progress
# ---------------------------------------------------------------------------

async def get_project_progress(
    session: AsyncSession,
    project_id: UUID,
) -> list[dict]:
    """Progress history for a project: % completed per period with delta."""
    stmt = (
        select(
            ProgressReportDB.id,
            ReportingPeriodDB.date.label("period_date"),
            ProgressReportDB.percentage,
            ProgressReportDB.delta,
        )
        .join(ReportingPeriodDB, ProgressReportDB.reporting_period_id == ReportingPeriodDB.id)
        .where(ProgressReportDB.project_id == project_id)
        .order_by(ReportingPeriodDB.date.desc())
    )

    result = await session.execute(stmt)
    return [
        {
            "id": str(r.id),
            "period_date": r.period_date,
            "percentage": _to_float(r.percentage),
            "delta": _to_float(r.delta),
        }
        for r in result.all()
    ]


# ---------------------------------------------------------------------------
# 6. tracker_get_periods
# ---------------------------------------------------------------------------

async def get_periods(
    session: AsyncSession,
    status: str | None = None,
) -> list[dict]:
    """Reporting periods with report count."""
    report_count_sq = (
        select(
            ReportDB.reporting_period_id,
            func.count(ReportDB.id).label("report_count"),
        )
        .group_by(ReportDB.reporting_period_id)
        .subquery()
    )

    confirmed_count_sq = (
        select(
            ReportDB.reporting_period_id,
            func.count(ReportDB.id).label("confirmed_count"),
        )
        .where(ReportDB.estimated.is_(False))
        .group_by(ReportDB.reporting_period_id)
        .subquery()
    )

    stmt = (
        select(
            ReportingPeriodDB.id,
            ReportingPeriodDB.date,
            ReportingPeriodDB.status,
            ReportingPeriodDB.base_rate,
            func.coalesce(report_count_sq.c.report_count, 0).label("report_count"),
            func.coalesce(confirmed_count_sq.c.confirmed_count, 0).label("confirmed_count"),
        )
        .outerjoin(report_count_sq, ReportingPeriodDB.id == report_count_sq.c.reporting_period_id)
        .outerjoin(confirmed_count_sq, ReportingPeriodDB.id == confirmed_count_sq.c.reporting_period_id)
        .order_by(ReportingPeriodDB.date.desc())
    )

    if status is not None:
        stmt = stmt.where(ReportingPeriodDB.status == status)

    result = await session.execute(stmt)
    return [
        {
            "id": str(r.id),
            "date": r.date,
            "status": r.status,
            "base_rate": _to_float(r.base_rate),
            "report_count": r.report_count,
            "confirmed_count": r.confirmed_count,
        }
        for r in result.all()
    ]


# ---------------------------------------------------------------------------
# 7. tracker_get_user_jira_issues
# ---------------------------------------------------------------------------

async def get_user_jira_issues(
    session: AsyncSession,
    user_id: UUID,
    start_date: str,
    end_date: str,
) -> dict:
    """Jira issues assigned to a user in a date range.

    Looks up the user's email, then queries Jira for issues that were
    In Progress or Done during the period.
    """
    from app.core.services.jira_client import JiraClient
    from app.core.services.oauth_service import OAuthService

    user = await session.get(UserDB, user_id)
    if not user:
        return {"error": f"User '{user_id}' not found"}

    jql = (
        f'assignee = "{user.email}" AND '
        f'updatedDate >= "{start_date}" AND updatedDate <= "{end_date}" AND '
        f'statusCategory in ("In Progress", "Done")'
    )

    client = JiraClient(db=session)
    try:
        http = await client.get_client()
        response = await http.post(
            "/rest/api/3/search/jql",
            json={
                "jql": jql,
                "fields": ["summary", "status", "project", "issuetype"],
                "maxResults": 50,
            },
        )

        if response.status_code != 200:
            logger.warning(
                "mcp_jira_query_failed",
                status_code=response.status_code,
                user_id=str(user_id),
            )
            return {"issues": [], "error": "Jira query failed"}

        data = response.json()
        issues = []
        for issue in data.get("issues", []):
            fields = issue.get("fields", {})
            project = fields.get("project", {})
            status = fields.get("status", {})
            issue_type = fields.get("issuetype", {})
            issues.append({
                "key": issue["key"],
                "summary": fields.get("summary", ""),
                "status": status.get("name", ""),
                "status_category": status.get("statusCategory", {}).get("name", ""),
                "project_key": project.get("key", ""),
                "project_name": project.get("name", ""),
                "issue_type": issue_type.get("name", ""),
            })

        site_info = await OAuthService.get_jira_site_info(session)
        site_url = site_info.get("site_url", "") if site_info else ""

        return {
            "user": user.email,
            "start_date": start_date,
            "end_date": end_date,
            "issue_count": len(issues),
            "issues": issues,
            "site_url": site_url,
        }
    except Exception as e:
        logger.warning("mcp_jira_fetch_failed", user_id=str(user_id), error=str(e))
        return {"issues": [], "error": f"Jira connection failed: {e}"}
    finally:
        await client.close()
