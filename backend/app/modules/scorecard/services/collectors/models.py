"""Typed models for collector return data."""

from datetime import date

from pydantic import BaseModel


class JiraCollectedMetrics(BaseModel):
    """Typed return model for Jira collector."""

    # defect_density
    bugs_total: int
    tasks_completed: int

    # escaped_rate
    escaped_defects: int

    # mttr
    incidents_count: int
    mttr_hours: float | None = None

    # story_review_ratio
    total_stories: int
    stories_with_reviewer: int

    # commitment_reliability
    commitment_reliability: float | None = None
    committed_issues: int
    single_sprint_issues: int
    multi_sprint_issues: int

    # lead_time
    lead_time_days: float | None = None
    lead_time_sample_size: int

    # post_contract_tasks
    post_contract_tasks: int | None = None
    post_contract_cutoff: date | str | None = None


class GitHubCollectedMetrics(BaseModel):
    """Typed return model for GitHub collector."""

    # pr_review
    prs_without_review: int
    total_merged_prs: int
    pr_review_ratio: float | None = None

    # pr_size
    pr_size_median: float | None = None

    # review_turnaround
    review_turnaround_hours: float | None = None

    # deployment_frequency
    deployment_frequency: float | None = None
    release_count_90d: int

    # change_failure_rate
    change_failure_rate: float | None = None
    total_releases: int
    failed_releases: int

    # vulnerabilities
    high_severity_vulns: int | None
    high_severity_vulns_total: int | None
