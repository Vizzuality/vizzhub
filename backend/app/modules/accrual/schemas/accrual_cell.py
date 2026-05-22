"""Pydantic schemas for ProjectAccrualCell."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AccrualCell(BaseModel):
    id: UUID
    project_id: UUID
    year: int
    month: int
    amount: Decimal
    is_manual_override: bool
    is_frozen: bool
    frozen_at: datetime | None
    frozen_rate: Decimal | None
    frozen_eur_amount: Decimal | None
    eur_amount: Decimal | None = None  # computed in the API layer (live cells)
    updated_at: datetime

    model_config = {"from_attributes": True}


class CellUpdate(BaseModel):
    amount: Decimal = Field(..., ge=0)


class BulkCellUpdate(BaseModel):
    project_id: UUID
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    amount: Decimal = Field(..., ge=0)


class BulkCellsRequest(BaseModel):
    updates: list[BulkCellUpdate]


class RedistributeRequest(BaseModel):
    force: bool = False
