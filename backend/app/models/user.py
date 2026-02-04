"""User model for Google SSO authentication."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class UserRole(str, Enum):
    """User roles for access control."""

    USER = "user"
    ADMIN = "admin"


class UserDB(Base):
    """SQLAlchemy model for users."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user", nullable=False)
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
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None
    role: UserRole = UserRole.USER


class UserCreate(UserBase):
    """Schema for creating a user (internal use)."""

    pass


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    role: UserRole | None = None


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
    first_name: str | None = None
    last_name: str | None = None
    picture: str | None = None
    role: UserRole

    model_config = {"from_attributes": True}
