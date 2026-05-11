"""Event database model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class EventDB(Base):
    """Corporate event tracked for participation and reporting."""

    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_events_rating_range"),
        CheckConstraint("other_costs >= 0", name="ck_events_other_costs_positive"),
        CheckConstraint(
            "attending IN ('yes','no','maybe')",
            name="ck_events_attending",
        ),
        Index("ix_events_start_date", "start_date"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    theme_primary: Mapped[str] = mapped_column(String(100), nullable=False)
    theme_secondary: Mapped[str | None] = mapped_column(String(100), nullable=True)
    region_focus: Mapped[str] = mapped_column(String(50), nullable=False)
    location_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    other_costs: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    attending: Mapped[str | None] = mapped_column(String(10), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
