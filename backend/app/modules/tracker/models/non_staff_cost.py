"""Non-personnel costs per project and period."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CostType(str, Enum):
    """Non-staff cost categories."""

    OUTSOURCE = "outsource"
    TRAVEL = "travel"
    SERVERS = "servers"
    OTHERS = "others"


class NonStaffCostDB(Base):
    """Non-staff cost entry."""

    __tablename__ = "non_staff_costs"
    __table_args__ = (
        CheckConstraint("cost >= 0", name="ck_non_staff_costs_cost_positive"),
        CheckConstraint(
            "cost_type IN ('outsource', 'travel', 'servers', 'others')",
            name="ck_non_staff_costs_type_valid",
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
    reporting_period_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("reporting_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_type: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
