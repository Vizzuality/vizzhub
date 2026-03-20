"""Pydantic schemas for invoices."""

import datetime as dt
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

VALID_STATUSES = ("scheduled", "pending_to_issue", "waiting_for_payment", "paid")

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "scheduled": [],
    "pending_to_issue": ["waiting_for_payment"],
    "waiting_for_payment": ["paid", "pending_to_issue"],
    "paid": ["waiting_for_payment"],
}


class InvoiceCreate(BaseModel):
    code: str | None = Field(None, max_length=100)
    amount: float = Field(ge=0)
    due_date: dt.date
    extended_date: dt.date | None = None
    invoiced_on: dt.date | None = None
    milestone: str = Field(min_length=1)
    observations: str | None = None
    status: str = "scheduled"


class InvoiceUpdate(BaseModel):
    code: str | None = None
    amount: float | None = Field(None, ge=0)
    due_date: dt.date | None = None
    extended_date: dt.date | None = None
    invoiced_on: dt.date | None = None
    milestone: str | None = None
    observations: str | None = None


class InvoiceTransition(BaseModel):
    status: str


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    code: str | None
    amount: float
    due_date: dt.date
    extended_date: dt.date | None
    invoiced_on: dt.date | None
    milestone: str
    observations: str | None
    status: str
