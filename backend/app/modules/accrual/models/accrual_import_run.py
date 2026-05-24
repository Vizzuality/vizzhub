"""AccrualImportRunDB — one row per importer execution (audit trail)."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AccrualImportRunDB(Base):
    """A single execution of the accrual importer.

    Holds totals and a raw_report blob (per-project diffs, warnings, etc.)
    so we can inspect any past run without re-parsing the spreadsheet.
    Excel rows and drift findings reference this row via FK.
    """

    __tablename__ = "accrual_import_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    rows_parsed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    rows_mapped: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    rows_unmatched: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    drift_findings_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    raw_report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    triggered_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
