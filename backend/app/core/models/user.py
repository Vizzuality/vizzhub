"""User model for Google SSO authentication."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class UserDB(Base):
    """SQLAlchemy model for users."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    functional_area_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("functional_areas.id", ondelete="SET NULL"),
        nullable=True,
    )
    rate_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("rates.id", ondelete="SET NULL"),
        nullable=True,
    )
    dedication: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    slack_user_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slack_display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UserBase(BaseModel):
    """Base user schema."""

    email: str
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None
    roles: list[str] = ["user"]
    functional_area_id: UUID | None = None
    rate_id: UUID | None = None
    dedication: Decimal | None = None
    slack_user_id: str | None = None
    slack_display_name: str | None = None
    active: bool = True


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    name: str | None = None
    functional_area_id: UUID | None = None
    rate_id: UUID | None = None
    dedication: Decimal | None = None
    active: bool | None = None


class User(UserBase):
    """Schema for user responses."""

    id: UUID
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    """Public user info (for JWT responses)."""

    id: UUID
    email: str
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None
    roles: list[str] = []
    permissions: list[str] = []
    active: bool = True

    model_config = {"from_attributes": True}
