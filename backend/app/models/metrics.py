from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StrategicImpact(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    TRANSFORMATIONAL = "transformational"


class ComplaintStatus(str, Enum):
    YES = "yes"
    NO = "no"
    NA = "-"


class Milestone(BaseModel):
    """Individual milestone data."""

    name: str
    planned_date: date
    actual_date: date | None = None
    criticality_weight: float = Field(default=1.0, ge=0)


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

    bugs_closed: int = Field(..., ge=0)
    tasks_completed: int = Field(..., ge=0)
    escaped_defects: int = Field(default=0, ge=0)
    mttr_hours: float | None = Field(default=None, ge=0)
    incidents_count: int = Field(default=0, ge=0)


class FlowMetrics(BaseModel):
    """Flow metrics from Jira."""

    lead_time_days: float | None = Field(default=None, ge=0)
    flow_efficiency: float | None = Field(default=None, ge=0, le=1)
    commitment_reliability: float | None = Field(default=None, ge=0, le=1)
    total_stories: int = Field(default=0, ge=0)
    stories_with_reviewer: int = Field(default=0, ge=0)


class GitHubMetrics(BaseModel):
    """Metrics from GitHub API."""

    prs_without_review: int = Field(default=0, ge=0)
    total_merged_prs: int = Field(default=0, ge=0)
    pr_review_ratio: float | None = Field(default=None, ge=0, le=1)
    high_severity_vulns: int = Field(default=0, ge=0, description="High vulns >30d")


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


class MetricsDB(Base):
    """SQLAlchemy model for raw metrics."""

    __tablename__ = "metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False
    )
    period_start: Mapped[date] = mapped_column(nullable=False)
    period_end: Mapped[date] = mapped_column(nullable=False)
    evm_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    milestones: Mapped[list | None] = mapped_column(JSON, nullable=True)
    jira_defects: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    flow_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    github_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    test_maturity: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    architecture: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pm_satisfaction: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    client_survey: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    strategic_impact: Mapped[str | None] = mapped_column(String(50), nullable=True)
    governance_exceptions: Mapped[int | None] = mapped_column(nullable=True)
    sev1_incident: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class MetricsCreate(BaseModel):
    """Schema for creating/updating metrics."""

    period_start: date
    period_end: date
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
    governance_exceptions: int | None = Field(default=None, ge=0)
    sev1_incident: bool = False


class Metrics(MetricsCreate):
    """Schema for metrics responses."""

    id: UUID
    project_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
