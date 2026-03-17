"""Pydantic schemas for non-staff costs."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tracker.models.non_staff_cost import CostType


class NonStaffCostCreate(BaseModel):
    project_id: UUID
    reporting_period_id: UUID
    cost: Decimal = Field(ge=0)
    cost_type: CostType
    details: str | None = None


class NonStaffCostUpdate(BaseModel):
    cost: Decimal | None = Field(default=None, ge=0)
    cost_type: CostType | None = None
    details: str | None = None


class NonStaffCostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    reporting_period_id: UUID
    cost: float
    cost_type: str
    details: str | None
    created_at: datetime
    updated_at: datetime
