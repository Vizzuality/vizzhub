from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import func

from app.database import Base


class ProjectStatus(str, Enum):
    """Project lifecycle status."""

    PROPOSAL = "proposal"
    LIVE = "live"
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
        CheckConstraint(
            "NOT (is_billable AND is_absence)",
            name="ck_projects_not_billable_and_absence",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    program_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="SET NULL"),
        nullable=True,
    )
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_absence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_scorecard: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    has_dependabot_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    has_budget_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(20), nullable=False, default="dollar")
    budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    locked_fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    original_budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    jira_project_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    github_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(nullable=True)
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="proposal", nullable=False)
    finished_at: Mapped[date | None] = mapped_column(nullable=True)
    slack_channel_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    project_manager_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=func.now()
    )

    @validates("status")
    def _validate_status(self, _key: str, value: str | ProjectStatus) -> str:
        """Reject typos at ORM-write time. Column stays `Mapped[str]` (no schema
        migration), but every write goes through `ProjectStatus(...)` so an
        unknown value raises before it reaches the DB. Audit Tier 1 #5."""
        if isinstance(value, ProjectStatus):
            return value.value
        return ProjectStatus(value).value


class ProjectBase(BaseModel):
    """Base project schema."""

    name: str = Field(..., min_length=1, max_length=255)
    program_id: UUID | None = None
    code: str | None = Field(None, max_length=100)
    is_billable: bool = True
    is_absence: bool = False
    has_scorecard: bool = True
    has_dependabot_alerts: bool = True
    has_budget_alerts: bool = True
    currency: str = Field("dollar", max_length=20)
    budget: float | None = Field(None, ge=0)
    locked_fx_rate: float | None = Field(None, ge=0)
    notes: str | None = None
    summary: str | None = None
    jira_project_key: str | None = Field(None, max_length=50)
    github_repo: str | None = Field(None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus = ProjectStatus.PROPOSAL
    finished_at: date | None = None
    slack_channel_id: str | None = Field(None, max_length=50)
    project_manager_id: UUID | None = None

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


class ProjectCreateV2(ProjectBase):
    """Schema for creating a project via /api/projects (code required)."""

    code: str = Field(..., min_length=1, max_length=100)


class ProjectUpdate(BaseModel):
    """Schema for partial updates (PATCH).

    Validators duplicate ProjectBase because Pydantic v2 field_validator
    requires the decorated method to live on the model class itself.
    A mixin base would need all-optional fields here but required in
    ProjectBase, so the duplication is the cleaner trade-off.
    """

    name: str | None = Field(None, min_length=1, max_length=255)
    program_id: UUID | None = None
    code: str | None = Field(None, max_length=100)
    is_billable: bool | None = None
    is_absence: bool | None = None
    has_scorecard: bool | None = None
    has_dependabot_alerts: bool | None = None
    has_budget_alerts: bool | None = None
    currency: str | None = Field(None, max_length=20)
    budget: float | None = Field(None, ge=0)
    locked_fx_rate: float | None = Field(None, ge=0)
    notes: str | None = None
    summary: str | None = None
    jira_project_key: str | None = Field(None, max_length=50)
    github_repo: str | None = Field(None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus | None = None
    finished_at: date | None = None
    slack_channel_id: str | None = Field(None, max_length=50)
    project_manager_id: UUID | None = None
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
    name: str = Field(..., min_length=0)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectResponse(Project):
    """Project response with resolved program and project manager names."""

    program_name: str | None = None
    project_manager_name: str | None = None
    original_budget: Decimal | None = None
