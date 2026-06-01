"""Read-only response schemas for the accrual dashboard summary endpoint."""

from typing import Literal

from pydantic import BaseModel

MonthStatus = Literal["recognized", "forecast"]


class DashboardMonth(BaseModel):
    """One calendar month of the selected year. ``recognized`` = already elapsed or
    sitting in a closed period; ``forecast`` = current/future months still to come."""

    month: int
    amount_eur: float
    status: MonthStatus


class DashboardKpis(BaseModel):
    """Headline figures. YTD/quarter scoped to the requested year; contracted and
    backlog are lifetime (all years)."""

    recognized_ytd_eur: float
    recognized_quarter_eur: float
    contracted_total_eur: float
    backlog_eur: float
    plan_recognized_pct: float


class DashboardSummary(BaseModel):
    """Full payload for GET /api/accrual/dashboard/summary."""

    year: int
    available_years: list[int]
    months: list[DashboardMonth]
    kpis: DashboardKpis
