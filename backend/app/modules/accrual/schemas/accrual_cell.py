"""Pydantic schemas for ProjectAccrualCell."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AccrualCell(BaseModel):
    """Cells store revenue in EUR directly. `frozen_eur_amount` is the snapshot
    captured at period close (= amount at that moment, immutable thereafter)."""

    id: UUID
    project_id: UUID
    year: int
    month: int
    amount: Decimal
    is_manual_override: bool
    is_frozen: bool
    frozen_at: datetime | None
    frozen_eur_amount: Decimal | None
    source: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class CellUpdate(BaseModel):
    amount: Decimal = Field(..., ge=0)


class LineCellUpsert(BaseModel):
    """Create-or-update a cell on a line at (year, month). The inline-edit path —
    keyed by ``line_id`` (route) so it works for multi-project and unlinked lines."""

    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    amount: Decimal = Field(..., ge=0)


class BulkCellUpdate(BaseModel):
    line_id: UUID
    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    amount: Decimal = Field(..., ge=0)


class BulkCellsRequest(BaseModel):
    updates: list[BulkCellUpdate]


class RedistributeRequest(BaseModel):
    force: bool = False
    include_frozen: bool = False
