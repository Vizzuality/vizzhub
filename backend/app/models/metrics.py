"""Metrics models - Hybrid approach with normalized columns + JSON for variable structures."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class StrategicImpact(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    TRANSFORMATIONAL = "transformational"


class SnapshotType(str, Enum):
    """Snapshot types for metrics records.

    PUNCTUAL: Data for a single month only (month start to month end)
    CUMULATIVE: Data from project start to month end
    """

    PUNCTUAL = "punctual"
    CUMULATIVE = "cumulative"


class ComplaintStatus(str, Enum):
    YES = "yes"
    NO = "no"
    NA = "-"


class Milestone(BaseModel):
    """Individual milestone data."""

    name: str
    planned_date: date
    actual_date: date | None = None


class TestMaturity(BaseModel):
    """Test maturity ratings (0-5 scale)."""

    e2e: int | None = Field(default=None, ge=0, le=5)
    unit: int | None = Field(default=None, ge=0, le=5)
    accessibility: int | None = Field(default=None, ge=0, le=5)
    security: int | None = Field(default=None, ge=0, le=5)
    frontend: int | None = Field(default=None, ge=0, le=5)


class ArchitectureChecklist(BaseModel):
    """Architecture documentation checklist."""

    docs_up_to_date: bool = False
    iac_implemented: bool = False
    adrs_maintained: bool = False
    diagrams_updated: bool = False


class PMSatisfaction(BaseModel):
    """PM estimation of client satisfaction."""

    delivery_complaints: ComplaintStatus = ComplaintStatus.NA
    design_complaints: ComplaintStatus = ComplaintStatus.NA
    overall_estimation: int | None = Field(default=None, ge=1, le=5)


class ClientSurvey(BaseModel):
    """End-of-project client satisfaction survey (1-5 scale)."""

    understanding: int | None = Field(default=None, ge=1, le=5)
    proactivity: int | None = Field(default=None, ge=1, le=5)
    communication: int | None = Field(default=None, ge=1, le=5)
    delivery_time: int | None = Field(default=None, ge=1, le=5)
    response_time: int | None = Field(default=None, ge=1, le=5)
    quality: int | None = Field(default=None, ge=1, le=5)
    expectations: int | None = Field(default=None, ge=1, le=5)
    recommend: int | None = Field(default=None, ge=1, le=5)


# Legacy Pydantic models for API compatibility (maps to/from DB columns)
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


class MetricsDB(Base):
    """SQLAlchemy model for metrics - Hybrid normalized + JSON."""

    __tablename__ = "metrics"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(nullable=False)
    period_end: Mapped[date] = mapped_column(nullable=False)

    # Period identification (for uniqueness constraint)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_type: Mapped[str] = mapped_column(
        String(20), default=SnapshotType.CUMULATIVE.value, nullable=False
    )

    # Config versioning (weights/targets at capture time)
    weights_applied: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    targets_applied: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # === EVM Data (normalized for SPI/CPI aggregation) ===
    budget_total: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    cost_to_date: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    percent_completed: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    percent_planned: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    # === Defect Metrics (normalized for trending) ===
    bugs_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tasks_completed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escaped_defects: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mttr_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    incidents_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    post_contract_tasks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # === Flow Metrics (normalized) ===
    lead_time_days: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    lead_time_sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commitment_reliability: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    committed_issues: Mapped[int | None] = mapped_column(Integer, nullable=True)
    single_sprint_issues: Mapped[int | None] = mapped_column(Integer, nullable=True)
    multi_sprint_issues: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_stories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stories_with_reviewer: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # === GitHub Metrics (normalized) ===
    prs_without_review: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_merged_prs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    high_severity_vulns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    high_severity_vulns_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_size_median: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    review_turnaround_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    deployment_frequency: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    release_count_90d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change_failure_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    total_releases: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_releases: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # === Manual/Simple fields (normalized) ===
    governance_exceptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sev1_incident: Mapped[bool] = mapped_column(Boolean, default=False)
    strategic_impact: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # === Variable structures (JSON) ===
    milestones: Mapped[list | None] = mapped_column(JSON, nullable=True)
    test_maturity: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    architecture: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pm_satisfaction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    client_survey: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # === Metadata ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Fields that are manually entered and should be preserved across collector runs
    MANUAL_FIELDS = [
        "sev1_incident",
        "budget_total",
        "cost_to_date",
        "percent_completed",
        "percent_planned",
        "governance_exceptions",
        "strategic_impact",
        "milestones",
        "pm_satisfaction",
        "test_maturity",
        "architecture",
        "client_survey",
    ]

    # Fields collected from GitHub (preserved when only running Jira collector)
    GITHUB_FIELDS = [
        "prs_without_review",
        "total_merged_prs",
        "high_severity_vulns",
        "high_severity_vulns_total",
        "pr_size_median",
        "review_turnaround_hours",
        "deployment_frequency",
        "release_count_90d",
        "change_failure_rate",
        "total_releases",
        "failed_releases",
    ]

    __table_args__ = (
        Index(
            "uq_metrics_project_period_type",
            "project_id",
            "period_year",
            "period_month",
            "snapshot_type",
            unique=True,
        ),
    )

    def get_preserved_fields(self, include_github: bool = True) -> dict:
        """Get dict of fields to preserve when creating new metrics.

        Args:
            include_github: Whether to include GitHub fields (False when running GitHub collector)

        Returns:
            Dict of field names to values for preservation
        """
        fields = self.MANUAL_FIELDS.copy()
        if include_github:
            fields.extend(self.GITHUB_FIELDS)

        return {field: getattr(self, field) for field in fields}

    @staticmethod
    def get_default_preserved_fields(include_github: bool = True) -> dict:
        """Get dict of default values for preserved fields when no existing metrics.

        Args:
            include_github: Whether to include GitHub fields

        Returns:
            Dict of field names to default values (None or False for sev1_incident)
        """
        fields = MetricsDB.MANUAL_FIELDS.copy()
        if include_github:
            fields.extend(MetricsDB.GITHUB_FIELDS)

        result = {field: None for field in fields}
        result["sev1_incident"] = False
        return result


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
        """Build EVMData from DB columns."""
        if db.budget_total is None:
            return None
        return EVMData(
            budget_total=float(db.budget_total),
            cost_to_date=float(db.cost_to_date) if db.cost_to_date else 0,
            percent_completed=float(db.percent_completed) if db.percent_completed else 0,
            percent_planned=float(db.percent_planned) if db.percent_planned else 0,
        )

    @staticmethod
    def _build_jira_defects(db: "MetricsDB") -> JiraDefectMetrics | None:
        """Build JiraDefectMetrics from DB columns."""
        if db.bugs_total is None and db.tasks_completed is None:
            return None
        return JiraDefectMetrics(
            bugs_total=db.bugs_total or 0,
            tasks_completed=db.tasks_completed or 0,
            escaped_defects=db.escaped_defects or 0,
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
    def _build_github_metrics(db: "MetricsDB") -> GitHubMetrics | None:
        """Build GitHubMetrics from DB columns."""
        if db.total_merged_prs is None and db.prs_without_review is None:
            return None

        pr_review_ratio = None
        if db.total_merged_prs and db.total_merged_prs > 0:
            reviewed = db.total_merged_prs - (db.prs_without_review or 0)
            pr_review_ratio = reviewed / db.total_merged_prs

        return GitHubMetrics(
            prs_without_review=db.prs_without_review or 0,
            total_merged_prs=db.total_merged_prs or 0,
            pr_review_ratio=pr_review_ratio,
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
    def from_db(cls, db: MetricsDB) -> "Metrics":
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
    This is a flattened view specifically for historical trend displays.
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

    model_config = {"from_attributes": True}
