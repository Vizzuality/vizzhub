"""Pydantic schemas for AccrualExcelRow + ImportRun."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AccrualExcelRow(BaseModel):
    id: UUID
    import_run_id: UUID
    import_run_position: int
    excel_code: str
    name: str | None
    pm_name: str | None
    client: str | None
    value_orig: Decimal | None
    currency: str | None
    rate: Decimal | None
    value_eur: Decimal
    start_date: date | None
    end_date: date | None
    months: int | None
    monthly_cells: list[dict[str, Any]] = Field(default_factory=list)
    # Populated when an accrual_alias exists for this excel_code. Lets the UI
    # show "Mapped to" and group rows aliased to the same tracker project.
    alias_project_id: UUID | None = None
    alias_project_name: str | None = None
    alias_project_code: str | None = None

    model_config = {"from_attributes": True}


class AccrualExcelRowsResponse(BaseModel):
    items: list[AccrualExcelRow]
    total: int
    import_run_id: UUID | None


class AccrualImportRun(BaseModel):
    id: UUID
    started_at: datetime
    completed_at: datetime | None
    source_path: str | None
    rows_parsed: int
    rows_mapped: int
    rows_unmatched: int
    drift_findings_count: int

    model_config = {"from_attributes": True}
