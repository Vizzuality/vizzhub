"""Capacity planning model — stores weekly allocation per project/user."""

from datetime import date, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base

_USERS_ID_FK = "users.id"


class CapacityPlanDB(Base):
    __tablename__ = "capacity_plans"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", "week_start", name="uq_capacity_plan_cell"),
        CheckConstraint("percentage >= 1 AND percentage <= 200", name="ck_capacity_plan_pct"),
        CheckConstraint(
            "EXTRACT(ISODOW FROM week_start) = 1",
            name="ck_capacity_plan_monday",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(_USERS_ID_FK, ondelete="CASCADE"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    percentage: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(_USERS_ID_FK, ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey(_USERS_ID_FK, ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CellUpdate(BaseModel):
    project_id: UUID
    user_id: UUID
    week_start: date
    percentage: int | None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("week_start")
    @classmethod
    def must_be_monday(cls, v: date) -> date:
        if v.isoweekday() != 1:
            raise ValueError("week_start must be a Monday")
        return v

    @field_validator("percentage")
    @classmethod
    def valid_range(cls, v: int | None) -> int | None:
        if v is not None and (v < 0 or v > 200):
            raise ValueError("percentage must be 0-200 or null")
        return v


class BulkCellUpdate(BaseModel):
    updates: list[CellUpdate]
