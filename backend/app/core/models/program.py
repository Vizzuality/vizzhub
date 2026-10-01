"""Programs — optional grouping of related projects."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Boolean, DateTime, String, false
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ProgramDB(Base):
    """SQLAlchemy model for programs."""

    __tablename__ = "programs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # Ops/admin buckets (Operations, Training…): hidden from the portfolio catalogue.
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Program(BaseModel):
    """Schema for program responses."""

    id: UUID
    name: str
    is_internal: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProgramCreate(BaseModel):
    """Schema for creating a program."""

    name: str = Field(..., min_length=1, max_length=255)


class ProgramUpdate(BaseModel):
    """Schema for renaming a program and/or flagging it internal (PATCH semantics)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    is_internal: bool | None = None

    @model_validator(mode="after")
    def _require_a_field(self) -> "ProgramUpdate":
        if self.name is None and self.is_internal is None:
            raise ValueError("Provide name and/or is_internal")
        return self
