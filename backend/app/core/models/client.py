"""Client — canonical, deduplicated customer entity (core)."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ClientDB(Base):
    __tablename__ = "clients"
    __table_args__ = (
        Index(
            "uq_clients_code",
            "code",
            unique=True,
            postgresql_where=text("code IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Client(BaseModel):
    id: UUID
    name: str
    slug: str
    code: str | None = None
    primary_contact: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    project_count: int = 0
    model_config = {"from_attributes": True}


class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    code: str | None = Field(None, max_length=255)
    primary_contact: str | None = Field(None, max_length=255)


class ClientUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    code: str | None = Field(None, max_length=255)
    primary_contact: str | None = Field(None, max_length=255)
    is_active: bool | None = None
