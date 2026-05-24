"""AccrualPeriodDB — open/closed lifecycle for accounting periods."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AccrualPeriodDB(Base):
    """Accounting period boundary used to freeze cells once closed.

    Only one open period at a time (enforced by partial unique index).
    Closed periods are immutable snapshots of all cells whose (year, month)
    falls within them. Status tracks lifecycle: open → closed via the
    scheduled close operation. Cells are stored in EUR directly, so no
    per-period FX rate snapshot is needed.
    """

    __tablename__ = "accrual_periods"
    __table_args__ = (
        UniqueConstraint("start_date", name="uq_accrual_periods_start_date"),
        CheckConstraint(
            "(closed_at IS NULL) = (status = 'open')",
            name="ck_accrual_periods_closed_status_consistent",
        ),
        Index(
            "uq_accrual_periods_one_open",
            "status",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
