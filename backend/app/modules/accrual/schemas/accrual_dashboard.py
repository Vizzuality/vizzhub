"""Read-only response schemas for the accrual dashboard summary endpoint."""

from typing import Literal

from pydantic import BaseModel

MonthStatus = Literal["recognized", "forecast"]


class DashboardMonth(BaseModel):
    """One calendar month of the selected year. ``recognized`` = already elapsed or
    sitting in a closed period; ``forecast`` = current/future months still to come.
    ``prev_amount_eur`` is the same calendar month one year earlier, for the YoY
    reference curve on the burn-up chart."""

    month: int
    amount_eur: float
    status: MonthStatus
    prev_amount_eur: float = 0.0


class DashboardKpis(BaseModel):
    """Headline figures. YTD/quarter scoped to the requested year; contracted and
    backlog are lifetime (all years). YoY compares the selected year's recognized
    months against the same months one year earlier (``yoy_pct`` is None when there
    is no prior-year recognition to compare against)."""

    recognized_ytd_eur: float
    full_year_eur: float
    recognized_quarter_eur: float
    contracted_total_eur: float
    backlog_eur: float
    plan_recognized_pct: float
    recognized_prev_ytd_eur: float
    yoy_pct: float | None = None


class DashboardSummary(BaseModel):
    """Full payload for GET /api/accrual/dashboard/summary."""

    year: int
    available_years: list[int]
    months: list[DashboardMonth]
    kpis: DashboardKpis
