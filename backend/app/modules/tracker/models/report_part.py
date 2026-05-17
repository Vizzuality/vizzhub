"""Time breakdown per report by project and functional area."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ReportPartDB(Base):
    """Time/cost entry for a specific project within a report."""

    __tablename__ = "report_parts"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "report_id",
            "functional_area_id",
            name="uq_report_parts_project_report_area",
        ),
        CheckConstraint(
            "percentage IS NULL OR (percentage >= 0 AND percentage <= 1)",
            name="ck_report_parts_percentage_range",
        ),
        CheckConstraint(
            "cost IS NULL OR cost >= 0",
            name="ck_report_parts_cost_positive",
        ),
        CheckConstraint(
            "days IS NULL OR days >= 0",
            name="ck_report_parts_days_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    functional_area_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("functional_areas.id", ondelete="SET NULL"),
        nullable=True,
    )
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    days: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
