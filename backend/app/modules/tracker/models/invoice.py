"""Invoice tracking with state machine."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class InvoiceDB(Base):
    """Invoice for a project."""

    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_invoices_amount_positive"),
        CheckConstraint(
            "status IN ('scheduled', 'pending_to_issue', 'waiting_for_payment', 'paid')",
            name="ck_invoices_status_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(nullable=False)
    invoiced_on: Mapped[date | None] = mapped_column(nullable=True)
    milestone: Mapped[str] = mapped_column(Text, nullable=False)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoicing_contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invoicing_contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
