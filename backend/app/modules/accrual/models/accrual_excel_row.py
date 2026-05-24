"""AccrualExcelRowDB — snapshot of each parsed Excel row."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AccrualExcelRowDB(Base):
    """One row of the CEO's accrual spreadsheet as parsed by the importer.

    Multiple rows can share the same excel_code within a run (e.g. FHWPC
    has Phase 1, 2a, 2b — same code, different months/values) — that's why
    the uniqueness constraint includes import_run_position.

    Queries against "the current Excel" should filter by the most recent
    import_run_id; older rows are retained for audit purposes.

    monthly_cells is a JSONB array: [{year, month, eur_amount}, ...].
    """

    __tablename__ = "accrual_excel_rows"
    __table_args__ = (
        UniqueConstraint(
            "import_run_id",
            "excel_code",
            "import_run_position",
            name="uq_accrual_excel_rows_run_code_pos",
        ),
        Index("ix_accrual_excel_rows_import_run", "import_run_id"),
        Index("ix_accrual_excel_rows_excel_code", "excel_code"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    import_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accrual_import_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    import_run_position: Mapped[int] = mapped_column(Integer, nullable=False)
    excel_code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    pm_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    client: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_orig: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    value_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, server_default="0")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_cells: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
