"""ProjectAccrualCellDB — per-project per-month accrual cell."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CellSource(StrEnum):
    """Where a cell's value came from. Mirrors the CHECK constraint in DB."""

    EXCEL = "excel"
    TEAM_BUDGET = "team_budget"
    MANUAL = "manual"


_CELL_SOURCES_CHECK = ", ".join(f"'{s.value}'" for s in CellSource)


class ProjectAccrualCellDB(Base):
    """One revenue-accrual cell per project per calendar month.

    Cells are created/updated by the redistribute_for_project service whenever
    tracker data changes. Amount is always in EUR (mirroring the CEO's source
    spreadsheet, where every monthly figure is already in EUR). A cell can be
    manually overridden (is_manual_override) which pins the amount and stops
    automatic redistribution from touching it. When an accrual period is closed,
    all cells for that period are frozen: frozen_at and frozen_eur_amount are
    set and the cell becomes immutable.
    """

    __tablename__ = "project_accrual_cells"
    __table_args__ = (
        UniqueConstraint("line_id", "year", "month", name="uq_accrual_cells_line_month"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_accrual_cells_month_range"),
        CheckConstraint("amount >= 0", name="ck_accrual_cells_amount_nonneg"),
        CheckConstraint(
            "(is_frozen = false) OR (frozen_at IS NOT NULL AND frozen_eur_amount IS NOT NULL)",
            name="ck_accrual_cells_frozen_consistency",
        ),
        CheckConstraint(
            f"source IN ({_CELL_SOURCES_CHECK})",
            name="ck_accrual_cells_source",
        ),
        Index("ix_accrual_cells_year_month", "year", "month"),
        Index("ix_accrual_cells_project", "project_id"),
        Index("ix_accrual_cells_line", "line_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    line_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accrual_lines.id", ondelete="CASCADE"),
        nullable=True,
    )
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    is_manual_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    frozen_eur_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=CellSource.EXCEL.value,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
