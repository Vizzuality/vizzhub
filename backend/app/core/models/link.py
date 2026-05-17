"""Generic links for programs and projects."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class LinkType(str, Enum):
    """Link type categories."""

    CODE = "code"
    PROJECT_MANAGEMENT = "project-management"
    APP_ENVIRONMENTS = "app-environments"
    DESIGN = "design"


class LinkDB(Base):
    """SQLAlchemy model for links."""

    __tablename__ = "links"
    __table_args__ = (
        CheckConstraint(
            "(program_id IS NOT NULL AND project_id IS NULL) "
            "OR (program_id IS NULL AND project_id IS NOT NULL)",
            name="ck_links_exactly_one_parent",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    program_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=True,
    )
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Link(BaseModel):
    """Schema for link responses."""

    id: UUID
    program_id: UUID | None = None
    project_id: UUID | None = None
    title: str | None = None
    url: str | None = None
    link_type: LinkType | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LinkCreate(BaseModel):
    """Schema for creating a link."""

    program_id: UUID | None = None
    project_id: UUID | None = None
    title: str | None = Field(None, max_length=255)
    url: str | None = Field(None, max_length=500)
    link_type: LinkType | None = None

    @model_validator(mode="after")
    def validate_exactly_one_parent(self) -> "LinkCreate":
        if self.program_id is not None and self.project_id is not None:
            raise ValueError("Link must belong to either a program or a project, not both")
        if self.program_id is None and self.project_id is None:
            raise ValueError("Link must belong to a program or a project")
        return self
