"""Budget allocation per project and functional area."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class BudgetLineDB(Base):
    """Budget line item."""

    __tablename__ = "budget_lines"
    __table_args__ = (
        CheckConstraint(
            "percentage IS NULL OR (percentage >= 0 AND percentage <= 1)",
            name="ck_budget_lines_percentage_range",
        ),
        CheckConstraint(
            "days IS NULL OR days >= 0",
            name="ck_budget_lines_days_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    functional_area_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("functional_areas.id", ondelete="SET NULL"),
        nullable=True,
    )
    days: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    details: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
