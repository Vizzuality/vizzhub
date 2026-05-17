"""Pydantic schemas for metrics API requests and responses."""

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .api_models import EVMData, FlowMetrics, GitHubMetrics, JiraDefectMetrics
from .embedded import (
    ArchitectureChecklist,
    ClientSurvey,
    Milestone,
    PMSatisfaction,
    TestMaturity,
)
from .enums import SnapshotType, StrategicImpact

if TYPE_CHECKING:
    from .db import MetricsDB


class MetricsCreate(BaseModel):
    """Schema for creating/updating metrics - uses nested models for API convenience."""

    period_start: date
    period_end: date

    # Period identification (for uniqueness constraint) - optional, derived from period_end
    period_year: int | None = Field(default=None, ge=2020, le=2100)
    period_month: int | None = Field(default=None, ge=1, le=12)
    snapshot_type: SnapshotType = Field(default=SnapshotType.CUMULATIVE)

    # Config versioning (weights/targets at capture time)
    weights_applied: dict = Field(default_factory=dict)
    targets_applied: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def derive_period_from_end_date(self) -> "MetricsCreate":
        """Derive period_year and period_month from period_end if not provided."""
        if self.period_year is None:
            self.period_year = self.period_end.year
        if self.period_month is None:
            self.period_month = self.period_end.month
        return self

    # Nested models for API grouping (flattened to columns in DB)
    evm_data: EVMData | None = None
    jira_defects: JiraDefectMetrics | None = None
    flow_metrics: FlowMetrics | None = None
    github_metrics: GitHubMetrics | None = None

    # Variable structures (stored as JSON)
    milestones: list[Milestone] | None = None
    test_maturity: TestMaturity | None = None
    architecture: ArchitectureChecklist | None = None
    pm_satisfaction: PMSatisfaction | None = None
    client_survey: ClientSurvey | None = None

    # Simple fields
    strategic_impact: StrategicImpact | None = None
    governance_exceptions: int | None = Field(default=None, ge=0)
    sev1_incident: bool = False

    def to_db_dict(self) -> dict:
        """Convert to flat dictionary for DB insertion."""
        data: dict = {
            "period_start": self.period_start,
            "period_end": self.period_end,
            "period_year": self.period_year,
            "period_month": self.period_month,
            "snapshot_type": self.snapshot_type.value,
            "weights_applied": self.weights_applied,
            "targets_applied": self.targets_applied,
            "governance_exceptions": self.governance_exceptions,
            "sev1_incident": self.sev1_incident,
            "strategic_impact": self.strategic_impact.value if self.strategic_impact else None,
            "milestones": [m.model_dump(mode="json") for m in self.milestones]
            if self.milestones
            else None,
            "test_maturity": self.test_maturity.model_dump() if self.test_maturity else None,
            "architecture": self.architecture.model_dump() if self.architecture else None,
            "pm_satisfaction": self.pm_satisfaction.model_dump() if self.pm_satisfaction else None,
            "client_survey": self.client_survey.model_dump() if self.client_survey else None,
        }

        # Flatten EVM data
        if self.evm_data:
            data["budget_total"] = self.evm_data.budget_total
            data["cost_to_date"] = self.evm_data.cost_to_date
            data["percent_completed"] = self.evm_data.percent_completed
            data["percent_planned"] = self.evm_data.percent_planned

        # Flatten Jira defects
        if self.jira_defects:
            data["bugs_total"] = self.jira_defects.bugs_total
            data["tasks_completed"] = self.jira_defects.tasks_completed
            data["escaped_defects"] = self.jira_defects.escaped_defects
            data["mttr_hours"] = self.jira_defects.mttr_hours
            data["incidents_count"] = self.jira_defects.incidents_count
            data["post_contract_tasks"] = self.jira_defects.post_contract_tasks

        # Flatten Flow metrics
        if self.flow_metrics:
            data["lead_time_days"] = self.flow_metrics.lead_time_days
            data["lead_time_sample_size"] = self.flow_metrics.lead_time_sample_size
            data["commitment_reliability"] = self.flow_metrics.commitment_reliability
            data["committed_issues"] = self.flow_metrics.committed_issues
            data["single_sprint_issues"] = self.flow_metrics.single_sprint_issues
            data["multi_sprint_issues"] = self.flow_metrics.multi_sprint_issues
            data["total_stories"] = self.flow_metrics.total_stories
            data["stories_with_reviewer"] = self.flow_metrics.stories_with_reviewer

        # Flatten GitHub metrics
        if self.github_metrics:
            data["prs_without_review"] = self.github_metrics.prs_without_review
            data["total_merged_prs"] = self.github_metrics.total_merged_prs
            data["high_severity_vulns"] = self.github_metrics.high_severity_vulns
            data["high_severity_vulns_total"] = self.github_metrics.high_severity_vulns_total
            data["pr_size_median"] = self.github_metrics.pr_size_median
            data["review_turnaround_hours"] = self.github_metrics.review_turnaround_hours
            data["deployment_frequency"] = self.github_metrics.deployment_frequency
            data["release_count_90d"] = self.github_metrics.release_count_90d
            data["change_failure_rate"] = self.github_metrics.change_failure_rate
            data["total_releases"] = self.github_metrics.total_releases
            data["failed_releases"] = self.github_metrics.failed_releases

        return data

    @staticmethod
    def _build_evm_data(db: "MetricsDB") -> EVMData | None:
        """Build EVMData from DB columns.

        Preserves NULL fields as None so downstream normalizers can
        distinguish "not measured" from "measured as zero". Previously
        defaulted everything to 0, which made SPI=0 for projects that
        had only set budget_total without any progress capture yet.
        """
        if db.budget_total is None:
            return None
        return EVMData(
            budget_total=float(db.budget_total),
            cost_to_date=float(db.cost_to_date) if db.cost_to_date is not None else None,
            percent_completed=(
                float(db.percent_completed) if db.percent_completed is not None else None
            ),
            percent_planned=(float(db.percent_planned) if db.percent_planned is not None else None),
        )

    @staticmethod
    def _build_jira_defects(db: "MetricsDB") -> JiraDefectMetrics | None:
        """Build JiraDefectMetrics from DB columns.

        Preserves NULL columns as None (instead of defaulting to 0) so
        the defect-density / escaped-rate normalizers can exclude missing
        data from the score instead of treating it as a perfect zero.
        """
        if db.bugs_total is None and db.tasks_completed is None:
            return None
        return JiraDefectMetrics(
            bugs_total=db.bugs_total,
            tasks_completed=db.tasks_completed,
            escaped_defects=db.escaped_defects,
            mttr_hours=float(db.mttr_hours) if db.mttr_hours is not None else None,
            incidents_count=db.incidents_count or 0,
            post_contract_tasks=db.post_contract_tasks,
        )

    @staticmethod
    def _build_flow_metrics(db: "MetricsDB") -> FlowMetrics | None:
        """Build FlowMetrics from DB columns."""
        if db.lead_time_days is None and db.total_stories is None:
            return None
        return FlowMetrics(
            lead_time_days=float(db.lead_time_days) if db.lead_time_days is not None else None,
            lead_time_sample_size=db.lead_time_sample_size or 0,
            commitment_reliability=float(db.commitment_reliability)
            if db.commitment_reliability is not None
            else None,
            committed_issues=db.committed_issues or 0,
            single_sprint_issues=db.single_sprint_issues or 0,
            multi_sprint_issues=db.multi_sprint_issues or 0,
            total_stories=db.total_stories or 0,
            stories_with_reviewer=db.stories_with_reviewer or 0,
        )

    @staticmethod
    def _compute_pr_review_ratio(db: "MetricsDB") -> float | None:
        """Compute PR review ratio from DB columns."""
        if not db.total_merged_prs or db.total_merged_prs <= 0:
            return None
        reviewed = db.total_merged_prs - (db.prs_without_review or 0)
        return reviewed / db.total_merged_prs

    @staticmethod
    def _build_github_metrics(db: "MetricsDB") -> GitHubMetrics | None:
        """Build GitHubMetrics from DB columns."""
        if db.total_merged_prs is None and db.prs_without_review is None:
            return None

        return GitHubMetrics(
            prs_without_review=db.prs_without_review or 0,
            total_merged_prs=db.total_merged_prs or 0,
            pr_review_ratio=MetricsCreate._compute_pr_review_ratio(db),
            high_severity_vulns=db.high_severity_vulns or 0,
            high_severity_vulns_total=db.high_severity_vulns_total or 0,
            pr_size_median=float(db.pr_size_median) if db.pr_size_median is not None else None,
            review_turnaround_hours=float(db.review_turnaround_hours)
            if db.review_turnaround_hours is not None
            else None,
            deployment_frequency=float(db.deployment_frequency)
            if db.deployment_frequency is not None
            else None,
            release_count_90d=db.release_count_90d or 0,
            change_failure_rate=float(db.change_failure_rate)
            if db.change_failure_rate is not None
            else None,
            total_releases=db.total_releases or 0,
            failed_releases=db.failed_releases or 0,
        )

    @classmethod
    def from_db(cls, db: "MetricsDB") -> "MetricsCreate":
        """Create from DB model, reconstructing nested structures."""
        return cls(
            period_start=db.period_start,
            period_end=db.period_end,
            period_year=db.period_year,
            period_month=db.period_month,
            snapshot_type=SnapshotType(db.snapshot_type),
            weights_applied=db.weights_applied or {},
            targets_applied=db.targets_applied or {},
            evm_data=cls._build_evm_data(db),
            jira_defects=cls._build_jira_defects(db),
            flow_metrics=cls._build_flow_metrics(db),
            github_metrics=cls._build_github_metrics(db),
            milestones=[Milestone(**m) for m in db.milestones] if db.milestones else None,
            test_maturity=TestMaturity(**db.test_maturity) if db.test_maturity else None,
            architecture=ArchitectureChecklist(**db.architecture) if db.architecture else None,
            pm_satisfaction=PMSatisfaction(**db.pm_satisfaction) if db.pm_satisfaction else None,
            client_survey=ClientSurvey(**db.client_survey) if db.client_survey else None,
            strategic_impact=StrategicImpact(db.strategic_impact) if db.strategic_impact else None,
            governance_exceptions=db.governance_exceptions,
            sev1_incident=db.sev1_incident,
        )


class Metrics(MetricsCreate):
    """Schema for metrics responses."""

    id: UUID
    project_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_db(cls, db: "MetricsDB") -> "Metrics":
        """Create response from DB model."""
        base = MetricsCreate.from_db(db)
        return cls(
            id=db.id,
            project_id=db.project_id,
            created_at=db.created_at,
            **base.model_dump(),
        )


class MetricsWithScores(BaseModel):
    """Schema for metrics responses with computed indicators and scores.

    Used for API responses that include both raw metrics and computed scores.
    Includes raw metrics data for period-specific views.
    """

    id: str
    project_id: str
    period_year: int
    period_month: int
    snapshot_type: str
    weights_applied: dict
    targets_applied: dict
    created_at: datetime
    indicators: dict
    scores: dict

    # Raw metrics data (for QualityMetricsGrid, DORASection, etc.)
    evm_data: EVMData | None = None
    milestones: list[Milestone] | None = None
    jira_defects: JiraDefectMetrics | None = None
    flow_metrics: FlowMetrics | None = None
    github_metrics: GitHubMetrics | None = None
    test_maturity: TestMaturity | None = None
    architecture: ArchitectureChecklist | None = None
    pm_satisfaction: PMSatisfaction | None = None
    client_survey: ClientSurvey | None = None
    strategic_impact: StrategicImpact | None = None
    governance_exceptions: int | None = None
    sev1_incident: bool = False

    model_config = {"from_attributes": True}
