from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
