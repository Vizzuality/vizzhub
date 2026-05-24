"""Project API schemas."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel

from app.core.models.project import Project
from app.core.schemas.common import PaginatedResponse

PaginatedProjectsResponse = PaginatedResponse[Project]


class ProjectSummary(BaseModel):
    """Lightweight project summary for dropdowns."""

    id: UUID
    name: str
    code: str | None = None
    currency: str | None = None
    budget: float | None = None
    start_date: date | None = None
    end_date: date | None = None

    model_config = {"from_attributes": True}
