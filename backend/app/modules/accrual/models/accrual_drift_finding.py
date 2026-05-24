"""AccrualDriftFindingDB — divergences flagged for human review."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func, text

from app.database import Base


class DriftKind(StrEnum):
    """Enum of drift finding kinds. Mirrors the CHECK constraint in DB."""

    DATE_EXTEND = "date_extend"
    DATE_SHRINK = "date_shrink"
    VALUE_DRIFT = "value_drift"
    STATUS_STALE = "status_stale"
    MISSING_EXCEL = "missing_excel"
    MISSING_TRACKER = "missing_tracker"


_DRIFT_KINDS_CHECK = ", ".join(f"'{k.value}'" for k in DriftKind)


class AccrualDriftFindingDB(Base):
    """A divergence between tracker state and the Excel snapshot.

    Kinds:
    - date_extend: Excel covers a later end_date than tracker → tracker stale.
    - date_shrink: Excel ends earlier than tracker → tracker over-allocated.
    - value_drift: Σ Excel cells diverges from tracker budget beyond threshold.
    - status_stale: tracker says 'live' but end_date is in the past.
    - missing_excel: tracker project has no Excel match.
    - missing_tracker: Excel row resolves to no tracker project.

    At least one of (project_id, excel_code) must be non-null (enforced by
    DB-level CHECK).
    """

    __tablename__ = "accrual_drift_findings"
    __table_args__ = (
        CheckConstraint(
            f"kind IN ({_DRIFT_KINDS_CHECK})",
            name="ck_accrual_drift_findings_kind",
        ),
        CheckConstraint(
            "project_id IS NOT NULL OR excel_code IS NOT NULL",
            name="ck_accrual_drift_findings_subject",
        ),
        Index("ix_accrual_drift_findings_kind", "kind"),
        Index("ix_accrual_drift_findings_project", "project_id"),
        Index("ix_accrual_drift_findings_excel_code", "excel_code"),
        Index(
            "ix_accrual_drift_findings_unresolved",
            "detected_at",
            postgresql_where=text("resolved_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    excel_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    import_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accrual_import_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
