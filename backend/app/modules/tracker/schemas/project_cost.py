"""Schemas for project cost aggregation responses."""

import datetime as dt
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PeriodCostBreakdown(BaseModel):
    period_id: UUID
    date: dt.date
    staff_cost: float
    non_staff_cost: float
    total: float
    parts_count: int


class ProjectCostSummary(BaseModel):
    project_id: UUID
    budget: float | None
    contract_rate: float
    staff_cost: float
    non_staff_cost: float
    total_cost: float
    burn_percentage: float | None
    periods: list[PeriodCostBreakdown]


class ProjectReportPartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    period_date: dt.date
    user_name: str | None
    user_email: str | None
    functional_area: str | None
    percentage: float | None
    days: float | None
    cost: float | None
    estimated: bool
