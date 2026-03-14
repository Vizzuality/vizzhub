"""Monthly reporting periods with state machine."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ReportingPeriodStatus(str, Enum):
    """Reporting period lifecycle."""

    UNSTARTED = "unstarted"
    ACTIVE = "active"
    FINISHED = "finished"


class ReportingPeriodDB(Base):
    """Monthly reporting period."""

    __tablename__ = "reporting_periods"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    date: Mapped[date] = mapped_column(Date(), nullable=False, unique=True)
    base_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="175.00"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unstarted"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
