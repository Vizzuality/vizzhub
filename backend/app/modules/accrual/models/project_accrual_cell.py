"""ProjectAccrualCellDB — per-project per-month accrual cell."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ProjectAccrualCellDB(Base):
    """One revenue-accrual cell per project per calendar month.

    Cells are created/updated by the redistribute_for_project service whenever
    tracker data changes. A cell can be manually overridden (is_manual_override)
    which pins the amount and stops automatic redistribution from touching it.
    When an accrual period is closed, all cells for that period are frozen:
    frozen_at, frozen_rate, and frozen_eur_amount are set and the cell becomes
    immutable.
    """

    __tablename__ = "project_accrual_cells"
    __table_args__ = (
        UniqueConstraint("project_id", "year", "month", name="uq_accrual_cells_project_month"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_accrual_cells_month_range"),
        CheckConstraint("amount >= 0", name="ck_accrual_cells_amount_nonneg"),
        CheckConstraint(
            "(is_frozen = false) OR "
            "(frozen_at IS NOT NULL AND frozen_rate IS NOT NULL AND frozen_eur_amount IS NOT NULL)",
            name="ck_accrual_cells_frozen_consistency",
        ),
        Index("ix_accrual_cells_year_month", "year", "month"),
        Index("ix_accrual_cells_project", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    is_manual_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frozen_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    frozen_eur_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
