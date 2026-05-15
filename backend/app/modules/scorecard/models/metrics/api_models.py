"""Pydantic models for API request/response metrics data."""

from pydantic import BaseModel, Field


class EVMData(BaseModel):
    """Earned Value Management data for P_time and P_cost.

    Only `budget_total` is required (it gates whether the project has any
    EVM at all). The other three are nullable so the deserializer can
    preserve "not yet measured" instead of silently defaulting to 0.
    Normalizers downstream (SPI/CPI/budget_variance) handle None.
    """

    budget_total: float = Field(..., ge=0, description="Planned Value total (PV)")
    cost_to_date: float | None = Field(default=None, ge=0, description="Actual Cost (AC)")
    percent_completed: float | None = Field(
        default=None, ge=0, le=1, description="Completion ratio 0-1 for EV calculation"
    )
    percent_planned: float | None = Field(
        default=None, ge=0, le=1, description="Planned progress ratio 0-1"
    )


class EVMDataPartial(BaseModel):
    """EVM data with all fields optional for project budget endpoint."""

    budget_total: float | None = Field(default=None, ge=0, description="Planned Value total (PV)")
    cost_to_date: float | None = Field(default=None, ge=0, description="Actual Cost (AC)")
    percent_completed: float | None = Field(
        default=None, ge=0, le=1, description="Completion ratio 0-1"
    )
    percent_planned: float | None = Field(
        default=None, ge=0, le=1, description="Planned progress ratio 0-1"
    )

    def to_evm_dict(self) -> dict:
        """Return only non-None fields as a flat dict for DB update."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class JiraDefectMetrics(BaseModel):
    """Defect and incident metrics from Jira.

    `bugs_total` and `tasks_completed` are nullable so the deserializer
    can preserve "not measured" instead of defaulting to 0. The defect-
    density / escaped-rate normalizers return None when the denominator
    is None or 0, so missing data is excluded from the score rather than
    counted as "perfect zero".
    """

    bugs_total: int | None = Field(default=None, ge=0)
    tasks_completed: int | None = Field(default=None, ge=0)
    escaped_defects: int | None = Field(default=None, ge=0)
    mttr_hours: float | None = Field(default=None, ge=0)
    incidents_count: int = Field(default=0, ge=0)
    post_contract_tasks: int | None = Field(
        default=None, ge=0, description="Tasks created >30 days after contract end"
    )


class FlowMetrics(BaseModel):
    """Flow metrics from Jira."""

    lead_time_days: float | None = Field(default=None, ge=0)
    lead_time_sample_size: int = Field(default=0, ge=0)
    commitment_reliability: float | None = Field(default=None, ge=0, le=1)
    committed_issues: int = Field(default=0, ge=0)
    single_sprint_issues: int = Field(default=0, ge=0)
    multi_sprint_issues: int = Field(default=0, ge=0)
    total_stories: int = Field(default=0, ge=0)
    stories_with_reviewer: int = Field(default=0, ge=0)


class GitHubMetrics(BaseModel):
    """Metrics from GitHub API."""

    prs_without_review: int = Field(default=0, ge=0)
    total_merged_prs: int = Field(default=0, ge=0)
    pr_review_ratio: float | None = Field(default=None, ge=0, le=1)
    high_severity_vulns: int = Field(
        default=0, ge=0, description="High/critical vulns open >30 days"
    )
    high_severity_vulns_total: int = Field(
        default=0, ge=0, description="Total open high/critical vulns"
    )
    pr_size_median: float | None = Field(default=None, ge=0, description="Median PR size in lines")
    review_turnaround_hours: float | None = Field(
        default=None, ge=0, description="Median hours to first review"
    )
    deployment_frequency: float | None = Field(
        default=None, ge=0, description="Releases per day (90d)"
    )
    release_count_90d: int = Field(default=0, ge=0, description="Number of releases in last 90 days")
    change_failure_rate: float | None = Field(
        default=None, ge=0, description="Change failure rate % (DORA)"
    )
    total_releases: int = Field(default=0, ge=0, description="Total releases for CFR calculation")
    failed_releases: int = Field(default=0, ge=0, description="Releases followed by patch/hotfix")
