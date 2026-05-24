"""Pydantic schemas for AccrualAlias."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AccrualAlias(BaseModel):
    id: UUID
    excel_code: str
    project_id: UUID
    project_name: str | None = None
    project_code: str | None = None
    weight: Decimal
    notes: str | None
    created_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AccrualAliasCreate(BaseModel):
    excel_code: str = Field(..., min_length=1, max_length=255)
    project_id: UUID
    weight: Decimal = Field(default=Decimal("1.0"), gt=0, le=1)
    notes: str | None = Field(default=None, max_length=1000)


class AccrualAliasUpdate(BaseModel):
    weight: Decimal | None = Field(default=None, gt=0, le=1)
    notes: str | None = Field(default=None, max_length=1000)


class AccrualAliasBulkMapping(BaseModel):
    project_id: UUID
    weight: Decimal = Field(default=Decimal("1.0"), gt=0, le=1)
    notes: str | None = Field(default=None, max_length=1000)


class AccrualAliasBulkCreate(BaseModel):
    excel_code: str = Field(..., min_length=1, max_length=255)
    mappings: list[AccrualAliasBulkMapping] = Field(..., min_length=1)
    replace_existing: bool = False
