"""Pydantic schemas for budget lines."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BudgetLineCreate(BaseModel):
    functional_area_id: UUID | None = None
    days: int = Field(ge=0)
    details: str | None = Field(None, max_length=255)


class BudgetLineBulkRequest(BaseModel):
    """Bulk replace all budget lines for a project."""

    lines: list[BudgetLineCreate]


class BudgetLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    functional_area_id: UUID | None
    functional_area_name: str | None = None
    days: int | None
    percentage: float | None
    details: str | None
