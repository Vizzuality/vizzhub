"""Billing rate bands (A, B, C, D)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class RateDB(Base):
    """SQLAlchemy model for rates."""

    __tablename__ = "rates"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Rate(BaseModel):
    """Schema for rate responses."""

    id: UUID
    code: str
    value: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RateCreate(BaseModel):
    """Schema for creating a rate."""

    code: str = Field(..., min_length=1, max_length=50)
    value: Decimal = Field(..., ge=0)
