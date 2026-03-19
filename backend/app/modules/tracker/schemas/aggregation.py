"""Schemas for generic project aggregation endpoint."""

import datetime as dt

from pydantic import BaseModel


class AggregationPeriod(BaseModel):
    date: dt.date
    days: float
    cost: float


class AggregationRow(BaseModel):
    name: str
    email: str | None = None
    total_days: float
    total_cost: float
    periods: list[AggregationPeriod]


class AggregationResponse(BaseModel):
    group_by: str
    rows: list[AggregationRow]
