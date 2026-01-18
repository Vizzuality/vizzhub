from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class IndicatorsDB(Base):
    """SQLAlchemy model for normalized indicators."""

    __tablename__ = "indicators"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    metrics_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("metrics.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    spi: Mapped[float | None] = mapped_column(nullable=True)
    on_time_milestones: Mapped[float | None] = mapped_column(nullable=True)
    cpi: Mapped[float | None] = mapped_column(nullable=True)
    budget_variance: Mapped[float | None] = mapped_column(nullable=True)
    defect_density: Mapped[float | None] = mapped_column(nullable=True)
    escaped_rate: Mapped[float | None] = mapped_column(nullable=True)
    mttr_hours: Mapped[float | None] = mapped_column(nullable=True)
    governance_compliance: Mapped[float | None] = mapped_column(nullable=True)
    lead_time_days: Mapped[float | None] = mapped_column(nullable=True)
    flow_efficiency: Mapped[float | None] = mapped_column(nullable=True)
    commitment_reliability: Mapped[float | None] = mapped_column(nullable=True)
    pr_review_ratio: Mapped[float | None] = mapped_column(nullable=True)
    prs_without_review: Mapped[int | None] = mapped_column(nullable=True)
    high_vulns: Mapped[int | None] = mapped_column(nullable=True)
    test_maturity: Mapped[float | None] = mapped_column(nullable=True)
    arch_checklist: Mapped[float | None] = mapped_column(nullable=True)
    story_review_ratio: Mapped[float | None] = mapped_column(nullable=True)
    okr_impact: Mapped[float | None] = mapped_column(nullable=True)
    pm_satisfaction: Mapped[float | None] = mapped_column(nullable=True)
    client_satisfaction: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IndicatorsCreate(BaseModel):
    """Schema for normalized indicators (all values 0-1 or raw for inverted)."""

    spi: float | None = Field(default=None, description="Schedule Performance Index")
    on_time_milestones: float | None = Field(
        default=None, ge=0, le=1, description="Weighted on-time milestone ratio"
    )
    cpi: float | None = Field(default=None, description="Cost Performance Index")
    budget_variance: float | None = Field(
        default=None, ge=0, description="Budget overrun percentage"
    )
    defect_density: float | None = Field(
        default=None, ge=0, description="Defects per 100 tasks"
    )
    escaped_rate: float | None = Field(
        default=None, ge=0, description="Escaped defects per 100 tasks"
    )
    mttr_hours: float | None = Field(
        default=None, ge=0, description="Mean time to recover in hours"
    )
    governance_compliance: float | None = Field(
        default=None, ge=0, le=1, description="Governance compliance score"
    )
    lead_time_days: float | None = Field(
        default=None, ge=0, description="Average lead time in days"
    )
    flow_efficiency: float | None = Field(
        default=None, ge=0, le=1, description="Active time / total time"
    )
    commitment_reliability: float | None = Field(
        default=None, ge=0, le=1, description="Completed / committed ratio"
    )
    pr_review_ratio: float | None = Field(
        default=None, ge=0, le=1, description="PRs with at least 1 review"
    )
    prs_without_review: int | None = Field(
        default=None, ge=0, description="Count of PRs merged without review"
    )
    high_vulns: int | None = Field(
        default=None, ge=0, description="High severity vulns >30 days"
    )
    test_maturity: float | None = Field(
        default=None, ge=0, le=1, description="Weighted test maturity score"
    )
    arch_checklist: float | None = Field(
        default=None, ge=0, le=1, description="Architecture checklist score (0-4 normalized)"
    )
    story_review_ratio: float | None = Field(
        default=None, ge=0, le=1, description="Stories with reviewer ratio"
    )
    okr_impact: float | None = Field(
        default=None, ge=0, le=1, description="Strategic impact score"
    )
    pm_satisfaction: float | None = Field(
        default=None, ge=0, le=1, description="PM satisfaction estimation"
    )
    client_satisfaction: float | None = Field(
        default=None, ge=0, le=1, description="Client survey score"
    )


class Indicators(IndicatorsCreate):
    """Schema for indicator responses."""

    id: UUID
    metrics_id: UUID
    project_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
