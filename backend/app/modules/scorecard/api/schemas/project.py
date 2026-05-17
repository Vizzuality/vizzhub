"""Project API schemas."""

from uuid import UUID

from pydantic import BaseModel

from app.core.models.project import Project
from app.core.schemas.common import PaginatedResponse

PaginatedProjectsResponse = PaginatedResponse[Project]


class ProjectSummary(BaseModel):
    """Lightweight project summary for dropdowns."""

    id: UUID
    name: str

    model_config = {"from_attributes": True}
