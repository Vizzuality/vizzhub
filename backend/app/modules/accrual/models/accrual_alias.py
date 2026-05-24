"""AccrualAliasDB — persistent N:M mapping Excel↔tracker with weights."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AccrualAliasDB(Base):
    """Persistent mapping from an Excel code to a tracker project.

    N:M cardinality with explicit weights:
    - 1:1 (most common): one alias row, weight=1.0
    - 1:N (one Excel row → multiple tracker projects, e.g. OEM split): N rows
      sharing excel_code, weights summing to 1.0
    - N:1 (multiple Excel rows → one tracker project, e.g. FHWPC phases):
      N rows sharing project_id, each weight=1.0 (each row contributes fully)
    """

    __tablename__ = "accrual_aliases"
    __table_args__ = (
        UniqueConstraint("excel_code", "project_id", name="uq_accrual_aliases_code_project"),
        CheckConstraint("weight > 0 AND weight <= 1", name="ck_accrual_aliases_weight_range"),
        Index("ix_accrual_aliases_excel_code", "excel_code"),
        Index("ix_accrual_aliases_project_id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    excel_code: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    weight: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False, server_default="1.0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
