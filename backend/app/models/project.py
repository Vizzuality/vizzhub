from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProjectDB(Base):
    """SQLAlchemy model for projects."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    jira_project_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    github_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=255)
    jira_project_key: str | None = Field(None, max_length=50)
    github_repo: str | None = Field(None, max_length=255, pattern=r"^[^/]+/[^/]+$")


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""

    name: str | None = Field(None, min_length=1, max_length=255)
    jira_project_key: str | None = Field(None, max_length=50)
    github_repo: str | None = Field(None, max_length=255, pattern=r"^[^/]+/[^/]+$")


class Project(ProjectBase):
    """Schema for project responses."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
