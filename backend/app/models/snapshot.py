"""Metric snapshot models for historical data."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.metrics import MetricsDB
    from app.models.project import ProjectDB


class MetricSnapshotDB(Base):
    """Monthly snapshot pointing to consolidated metrics with config versioning.

    The snapshot is a lightweight record that:
    - Points to a consolidated metrics record for the period
    - Preserves the weights/targets applied at snapshot time
    - Enables recalculation with original OR current config
    """

    __tablename__ = "metric_snapshots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    metrics_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("metrics.id", ondelete="RESTRICT"),
        nullable=False,
    )

    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(20), default="monthly")

    weights_applied: Mapped[dict] = mapped_column(JSONB, nullable=False)
    targets_applied: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    project: Mapped["ProjectDB"] = relationship(back_populates="snapshots")
    metrics: Mapped["MetricsDB"] = relationship()

    __table_args__ = (
        Index("idx_snapshot_project_period", "project_id", "period_year", "period_month"),
        Index(
            "uq_snapshot_project_month",
            "project_id",
            "period_year",
            "period_month",
            unique=True,
        ),
    )


class SnapshotCreate(BaseModel):
    """Request body for creating a snapshot."""

    period_year: int = Field(..., ge=2020, le=2100)
    period_month: int = Field(..., ge=1, le=12)


class ConfigSnapshot(BaseModel):
    """Preserved config at snapshot time."""

    weights: dict
    targets: dict


class SnapshotResponse(BaseModel):
    """Response schema for snapshots."""

    id: str
    project_id: str
    metrics_id: str
    period_year: int
    period_month: int
    snapshot_type: str
    config_applied: ConfigSnapshot
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_db(cls, db_model: MetricSnapshotDB) -> "SnapshotResponse":
        """Convert DB model to response schema."""
        return cls(
            id=str(db_model.id),
            project_id=str(db_model.project_id),
            metrics_id=str(db_model.metrics_id),
            period_year=db_model.period_year,
            period_month=db_model.period_month,
            snapshot_type=db_model.snapshot_type,
            config_applied=ConfigSnapshot(
                weights=db_model.weights_applied,
                targets=db_model.targets_applied,
            ),
            created_at=db_model.created_at,
        )
