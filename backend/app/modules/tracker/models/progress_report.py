"""Project completion tracking per period."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ProgressReportDB(Base):
    """Progress tracking for a project in a reporting period."""

    __tablename__ = "progress_reports"
    __table_args__ = (
        UniqueConstraint(
            "reporting_period_id",
            "project_id",
            name="uq_progress_reports_period_project",
        ),
        CheckConstraint(
            "percentage >= 0 AND percentage <= 1",
            name="ck_progress_reports_percentage_range",
        ),
        CheckConstraint(
            "delta >= -1 AND delta <= 1",
            name="ck_progress_reports_delta_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    reporting_period_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reporting_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    delta: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
