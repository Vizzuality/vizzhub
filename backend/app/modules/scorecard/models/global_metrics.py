"""Global Metrics models - Averaged metrics across all projects."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class GlobalMetricsDB(Base):
    """Stores averaged metrics across all projects for a given month.

    Follows the same pattern as MetricsDB with period-based storage.
    Each indicator stores both the averaged value and the count of projects
    that contributed to that average (only projects with data count).
    """

    __tablename__ = "global_metrics"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Total projects with any metrics for this period
    project_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # === Averaged Indicators (0-1 scale) + project counts ===
    spi: Mapped[float | None] = mapped_column(Float, nullable=True)
    spi_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    cpi: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpi_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    on_time_milestones: Mapped[float | None] = mapped_column(Float, nullable=True)
    on_time_milestones_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    defect_density: Mapped[float | None] = mapped_column(Float, nullable=True)
    defect_density_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    escaped_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    escaped_rate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    mttr_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    mttr_hours_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    governance_compliance: Mapped[float | None] = mapped_column(Float, nullable=True)
    governance_compliance_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    lead_time_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    lead_time_days_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    deployment_frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    deployment_frequency_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    change_failure_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_failure_rate_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    commitment_reliability: Mapped[float | None] = mapped_column(Float, nullable=True)
    commitment_reliability_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    pr_review_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    pr_review_ratio_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    test_maturity: Mapped[float | None] = mapped_column(Float, nullable=True)
    test_maturity_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    arch_checklist: Mapped[float | None] = mapped_column(Float, nullable=True)
    arch_checklist_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    high_vulns: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_vulns_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    okr_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    okr_impact_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    pm_satisfaction: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm_satisfaction_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    client_satisfaction: Mapped[float | None] = mapped_column(Float, nullable=True)
    client_satisfaction_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    story_review_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    story_review_ratio_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    strategic_impact: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategic_impact_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # === Averaged Dimension Scores (0-100 scale) + counts ===
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    p_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_time_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    p_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_cost_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    p_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_quality_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    p_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_value_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    p_satisfaction: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_satisfaction_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    p_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_flow_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    p_engineering: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_engineering_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    p_risk: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_risk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # === Budget-weighted scores (audit #17 weighting decision, 2026-05-15) ===
    # Same 0-100 scale, weighted by project.budget. Projects without budget are
    # excluded from this aggregate. budget_weighted_project_count tracks how
    # many projects contributed.
    budget_weighted_project_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_by_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_time_by_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_cost_by_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_quality_by_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_value_by_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_satisfaction_by_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_flow_by_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_engineering_by_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_risk_by_budget: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("period_year", "period_month", name="uq_global_metrics_period"),
    )


# === Pydantic Schemas ===


class IndicatorValue(BaseModel):
    """Indicator with its averaged value and project count."""

    value: float | None = None
    count: int = 0


class GlobalIndicators(BaseModel):
    """Averaged indicators across all projects."""

    spi: IndicatorValue = Field(default_factory=IndicatorValue)
    cpi: IndicatorValue = Field(default_factory=IndicatorValue)
    on_time_milestones: IndicatorValue = Field(default_factory=IndicatorValue)
    defect_density: IndicatorValue = Field(default_factory=IndicatorValue)
    escaped_rate: IndicatorValue = Field(default_factory=IndicatorValue)
    mttr_hours: IndicatorValue = Field(default_factory=IndicatorValue)
    governance_compliance: IndicatorValue = Field(default_factory=IndicatorValue)
    lead_time_days: IndicatorValue = Field(default_factory=IndicatorValue)
    deployment_frequency: IndicatorValue = Field(default_factory=IndicatorValue)
    change_failure_rate: IndicatorValue = Field(default_factory=IndicatorValue)
    commitment_reliability: IndicatorValue = Field(default_factory=IndicatorValue)
    pr_review_ratio: IndicatorValue = Field(default_factory=IndicatorValue)
    test_maturity: IndicatorValue = Field(default_factory=IndicatorValue)
    arch_checklist: IndicatorValue = Field(default_factory=IndicatorValue)
    high_vulns: IndicatorValue = Field(default_factory=IndicatorValue)
    okr_impact: IndicatorValue = Field(default_factory=IndicatorValue)
    pm_satisfaction: IndicatorValue = Field(default_factory=IndicatorValue)
    client_satisfaction: IndicatorValue = Field(default_factory=IndicatorValue)
    story_review_ratio: IndicatorValue = Field(default_factory=IndicatorValue)
    strategic_impact: IndicatorValue = Field(default_factory=IndicatorValue)


class ScoreValue(BaseModel):
    """Score with its averaged value and project count."""

    value: float | None = None
    count: int = 0


class GlobalScores(BaseModel):
    """Averaged dimension scores across all projects."""

    score: ScoreValue = Field(default_factory=ScoreValue)
    p_time: ScoreValue = Field(default_factory=ScoreValue)
    p_cost: ScoreValue = Field(default_factory=ScoreValue)
    p_quality: ScoreValue = Field(default_factory=ScoreValue)
    p_value: ScoreValue = Field(default_factory=ScoreValue)
    p_satisfaction: ScoreValue = Field(default_factory=ScoreValue)
    p_flow: ScoreValue = Field(default_factory=ScoreValue)
    p_engineering: ScoreValue = Field(default_factory=ScoreValue)
    p_risk: ScoreValue = Field(default_factory=ScoreValue)


class BudgetWeightedScores(BaseModel):
    """Budget-weighted version of GlobalScores.

    Same dimensions, but each score is a weighted average of project scores
    using project.budget as the weight. Projects without a budget are
    excluded; `project_count` reports how many contributed. Assumes
    all budgets are already in the portfolio's base currency (EUR).
    """

    project_count: int = 0
    score: float | None = None
    p_time: float | None = None
    p_cost: float | None = None
    p_quality: float | None = None
    p_value: float | None = None
    p_satisfaction: float | None = None
    p_flow: float | None = None
    p_engineering: float | None = None
    p_risk: float | None = None


class GlobalMetricsRecord(BaseModel):
    """Response for a stored global metrics record."""

    id: str
    period_year: int
    period_month: int
    project_count: int
    indicators: GlobalIndicators
    scores: GlobalScores
    # Budget-weighted aggregate. Null fields when no budgeted projects
    # contributed (legacy rows before audit #17 will have this empty).
    scores_by_budget: BudgetWeightedScores = Field(default_factory=BudgetWeightedScores)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_db(cls, db: GlobalMetricsDB) -> "GlobalMetricsRecord":
        """Create response from DB model."""
        indicator_fields = [
            "spi", "cpi", "on_time_milestones", "defect_density", "escaped_rate",
            "mttr_hours", "governance_compliance", "lead_time_days", "deployment_frequency",
            "change_failure_rate", "commitment_reliability", "pr_review_ratio",
            "test_maturity", "arch_checklist", "high_vulns", "okr_impact",
            "pm_satisfaction", "client_satisfaction", "story_review_ratio", "strategic_impact",
        ]

        score_fields = [
            "score", "p_time", "p_cost", "p_quality", "p_value",
            "p_satisfaction", "p_flow", "p_engineering", "p_risk",
        ]

        indicators_data = {}
        for field in indicator_fields:
            indicators_data[field] = IndicatorValue(
                value=getattr(db, field),
                count=getattr(db, f"{field}_count") or 0,
            )

        scores_data = {}
        for field in score_fields:
            scores_data[field] = ScoreValue(
                value=getattr(db, field),
                count=getattr(db, f"{field}_count") or 0,
            )

        by_budget_data: dict[str, float | int | None] = {
            "project_count": getattr(db, "budget_weighted_project_count", None) or 0,
        }
        for field in score_fields:
            by_budget_data[field] = getattr(db, f"{field}_by_budget", None)

        return cls(
            id=str(db.id),
            period_year=db.period_year,
            period_month=db.period_month,
            project_count=db.project_count,
            indicators=GlobalIndicators(**indicators_data),
            scores=GlobalScores(**scores_data),
            scores_by_budget=BudgetWeightedScores(**by_budget_data),
            created_at=db.created_at,
            updated_at=db.updated_at,
        )


class GlobalMetricsHistoryResponse(BaseModel):
    """Response for historical global metrics query."""

    records: list[GlobalMetricsRecord]


class CalculateBatchRequest(BaseModel):
    """Request to calculate global metrics for a date range."""

    from_year: int = Field(..., ge=2023, le=2100)
    from_month: int = Field(..., ge=1, le=12)
    to_year: int = Field(..., ge=2023, le=2100)
    to_month: int = Field(..., ge=1, le=12)


class CalculateBatchResponse(BaseModel):
    """Response from batch calculation."""

    months_processed: int
    records: list[GlobalMetricsRecord]
