from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ProjectStatus(str, Enum):
    """Project lifecycle status."""

    IN_PROGRESS = "in_progress"
    FINISHED = "finished"


def _strip_or_none(value: str | None) -> str | None:
    """Strip whitespace and convert empty strings to None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


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
    value = _strip_or_none(value)
    if value is not None and "/" not in value:
        raise ValueError("GitHub repo must be in format: owner/repo")
    if value is not None and value.count("/") != 1:
        raise ValueError("GitHub repo must be in format: owner/repo")
    return value


class ProjectDB(Base):
    """SQLAlchemy model for projects."""

    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_projects_end_after_start",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    program_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="SET NULL"),
        nullable=True,
    )
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    currency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    jira_project_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    github_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(nullable=True)
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    finished_at: Mapped[date | None] = mapped_column(nullable=True)
    slack_channel_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=255)
    program_id: UUID | None = None
    code: str | None = Field(None, max_length=100)
    is_billable: bool = True
    currency: str | None = Field(None, max_length=20)
    notes: str | None = None
    summary: str | None = None
    jira_project_key: str | None = Field(None, max_length=50)
    github_repo: str | None = Field(None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus = ProjectStatus.IN_PROGRESS
    finished_at: date | None = None
    slack_channel_id: str | None = Field(None, max_length=50)

    @field_validator("jira_project_key")
    @classmethod
    def sanitize_jira_key(cls, v: str | None) -> str | None:
        return _strip_or_none(v)

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
    program_id: UUID | None = None
    code: str | None = Field(None, max_length=100)
    is_billable: bool | None = None
    currency: str | None = Field(None, max_length=20)
    notes: str | None = None
    summary: str | None = None
    jira_project_key: str | None = Field(None, max_length=50)
    github_repo: str | None = Field(None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus | None = None
    finished_at: date | None = None
    slack_channel_id: str | None = Field(None, max_length=50)
    clear_finished_at: bool = False

    @field_validator("jira_project_key")
    @classmethod
    def sanitize_jira_key(cls, v: str | None) -> str | None:
        return _strip_or_none(v)

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
