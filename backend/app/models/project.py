from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ProjectStatus(str, Enum):
    """Project lifecycle status."""

    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


def validate_github_repo_format(value: str | None) -> str | None:
    """
    Validate GitHub repo format.

    Args:
        value: GitHub repo string or None

    Returns:
        Validated repo string or None

    Raises:
        ValueError: If repo format is invalid
    """
    if value is not None and "/" not in value:
        raise ValueError("GitHub repo must be in format: owner/repo")
    if value is not None and value.count("/") != 1:
        raise ValueError("GitHub repo must be in format: owner/repo")
    return value


class ProjectDB(Base):
    """SQLAlchemy model for projects."""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    jira_project_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    github_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(nullable=True)
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    finished_at: Mapped[date | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=255)
    jira_project_key: str | None = Field(None, max_length=50)
    github_repo: str | None = Field(None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus = ProjectStatus.IN_PROGRESS
    finished_at: date | None = None

    @field_validator("github_repo")
    @classmethod
    def validate_github_repo(cls, v: str | None) -> str | None:
        return validate_github_repo_format(v)

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectBase":
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be after start_date")
        return self


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for partial updates (PATCH)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    jira_project_key: str | None = Field(None, max_length=50)
    github_repo: str | None = Field(None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus | None = None
    finished_at: date | None = None
    clear_finished_at: bool = False  # Set to true to explicitly clear finished_at

    @field_validator("github_repo")
    @classmethod
    def validate_github_repo(cls, v: str | None) -> str | None:
        return validate_github_repo_format(v)


class Project(ProjectBase):
    """Schema for project responses."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
