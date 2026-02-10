"""Project API schemas."""

from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.common import PaginatedResponse
from app.models.project import Project

PaginatedProjectsResponse = PaginatedResponse[Project]


class ProjectSummary(BaseModel):
    """Lightweight project summary for dropdowns."""

    id: UUID
    name: str

    model_config = {"from_attributes": True}
