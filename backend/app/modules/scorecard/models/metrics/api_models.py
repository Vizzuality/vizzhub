"""Pydantic models for API request/response metrics data."""

from pydantic import BaseModel, Field


class EVMData(BaseModel):
    """Earned Value Management data for P_time and P_cost."""

    budget_total: float = Field(..., ge=0, description="Planned Value total (PV)")
    cost_to_date: float = Field(..., ge=0, description="Actual Cost (AC)")
    percent_completed: float = Field(
        ..., ge=0, le=1, description="Completion ratio 0-1 for EV calculation"
    )
    percent_planned: float = Field(
        ..., ge=0, le=1, description="Planned progress ratio 0-1"
    )


class JiraDefectMetrics(BaseModel):
    """Defect and incident metrics from Jira."""

    bugs_total: int = Field(..., ge=0)
    tasks_completed: int = Field(..., ge=0)
    escaped_defects: int = Field(default=0, ge=0)
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
