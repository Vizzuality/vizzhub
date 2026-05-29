"""AccrualLineDB — the revenue-recognition unit (replaces per-project keying).

A line is one unit of recognised revenue: an Excel row, a grant, a contract, or
a manual entry. Cells hang off the line (``accrual_cells.line_id``), not the
project, so two overlapping contracts on the same project keep distinct cells.

A line links to 0..N projects via ``accrual_line_projects``:
- N projects: one grant spanning sibling projects.
- 0 projects: an *unlinked* line — real income with no tracker project (future
  grant, untracked revenue). Still counts toward the company accrual total.

The line carries an editable ``window`` (``window_start``/``window_end``) that is
initialised from ``union(linked contract dates, Excel span)`` but is decoupled
from the contract: the CEO moves it freely (projects slip; revenue is recognised
later). The tracker contract is never written by accrual — it is ground truth.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class LineSource(StrEnum):
    """Where a line originated. Mirrors the CHECK constraint in DB."""

    EXCEL = "excel"
    TEAM_BUDGET = "team_budget"
    MANUAL = "manual"


_LINE_SOURCES_CHECK = ", ".join(f"'{s.value}'" for s in LineSource)


class AccrualLineDB(Base):
    """One revenue-recognition line. See module docstring."""

    __tablename__ = "accrual_lines"
    __table_args__ = (
        CheckConstraint(
            f"source IN ({_LINE_SOURCES_CHECK})",
            name="ck_accrual_lines_source",
        ),
        CheckConstraint("value_eur >= 0", name="ck_accrual_lines_value_nonneg"),
        Index("ix_accrual_lines_excel_code", "excel_code"),
        Index("ix_accrual_lines_import_run", "import_run_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=LineSource.MANUAL.value
    )
    excel_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    import_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accrual_import_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    value_orig: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    value_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    window_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    window_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
