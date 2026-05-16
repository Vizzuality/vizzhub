from pydantic import BaseModel, Field


class IndicatorsCreate(BaseModel):
    """Schema for normalized indicators (all values 0-1 or raw for inverted)."""

    spi: float | None = Field(default=None, description="Schedule Performance Index")
    on_time_milestones: float | None = Field(
        default=None, ge=0, le=1, description="Weighted on-time milestone ratio"
    )
    cpi: float | None = Field(default=None, description="Cost Performance Index")
    cost_variance_pct: float | None = Field(
        default=None,
        description=(
            "Signed Cost Variance / BAC (EVM): percent_completed - cost_to_date / "
            "budget_total. Negative = overrun relative to value delivered. "
            "No clamp — under-delivery and over-delivery are both meaningful."
        ),
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
    pr_size_median: float | None = Field(
        default=None, ge=0, description="Median PR size in lines"
    )
    review_turnaround_hours: float | None = Field(
        default=None, ge=0, description="Median hours to first review"
    )
    deployment_frequency: float | None = Field(
        default=None, ge=0, description="Releases per day (90d)"
    )
    change_failure_rate: float | None = Field(
        default=None, ge=0, le=100, description="Change failure rate % (DORA)"
    )
    post_contract_tasks: int | None = Field(
        default=None, ge=0, description="Tasks created >30 days after contract end"
    )
