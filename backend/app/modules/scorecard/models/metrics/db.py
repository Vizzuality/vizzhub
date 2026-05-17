"""SQLAlchemy model for metrics - Hybrid normalized + JSON."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base

from .enums import SnapshotType


class MetricsDB(Base):
    """SQLAlchemy model for metrics - Hybrid normalized + JSON."""

    __tablename__ = "metrics"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
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
    change_failure_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Fields that are manually entered and should be preserved across collector runs
    MANUAL_FIELDS = [
        "sev1_incident",
        "budget_total",
        "governance_exceptions",
        "strategic_impact",
        "milestones",
        "pm_satisfaction",
        "test_maturity",
        "architecture",
        "client_survey",
    ]

    # EVM fields populated from tracker/project data (not manually entered)
    TRACKER_EVM_FIELDS = [
        "cost_to_date",
        "percent_completed",
        "percent_planned",
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

        result = dict.fromkeys(fields, None)
        result["sev1_incident"] = False
        return result

    # Field mappings from collector data to DB columns
    JIRA_FIELD_MAPPING = {
        # Defect metrics
        "bugs_total": ("bugs_total", 0),
        "tasks_completed": ("tasks_completed", 0),
        "escaped_defects": ("escaped_defects", 0),
        "mttr_hours": ("mttr_hours", None),
        "incidents_count": ("incidents_count", 0),
        "post_contract_tasks": ("post_contract_tasks", None),
        # Flow metrics
        "lead_time_days": ("lead_time_days", None),
        "lead_time_sample_size": ("lead_time_sample_size", 0),
        "commitment_reliability": ("commitment_reliability", None),
        "committed_issues": ("committed_issues", 0),
        "single_sprint_issues": ("single_sprint_issues", 0),
        "multi_sprint_issues": ("multi_sprint_issues", 0),
        "total_stories": ("total_stories", 0),
        "stories_with_reviewer": ("stories_with_reviewer", 0),
    }

    GITHUB_FIELD_MAPPING = {
        "prs_without_review": ("prs_without_review", 0),
        "total_merged_prs": ("total_merged_prs", 0),
        "high_severity_vulns": ("high_severity_vulns", 0),
        "high_severity_vulns_total": ("high_severity_vulns_total", 0),
        "pr_size_median": ("pr_size_median", None),
        "review_turnaround_hours": ("review_turnaround_hours", None),
        "deployment_frequency": ("deployment_frequency", None),
        "release_count_90d": ("release_count_90d", 0),
        "change_failure_rate": ("change_failure_rate", None),
        "total_releases": ("total_releases", 0),
        "failed_releases": ("failed_releases", 0),
    }

    @classmethod
    def from_collector_data(
        cls,
        project_id: str,
        period_start: date,
        period_end: date,
        snapshot_type: SnapshotType,
        jira_data: dict | None = None,
        github_data: dict | None = None,
        preserved: dict | None = None,
    ) -> "MetricsDB":
        """Create MetricsDB instance from collector data.

        Centralizes the logic for building metrics from Jira/GitHub collector output.

        Args:
            project_id: UUID of the project as string
            period_start: Start date for the metrics period
            period_end: End date for the metrics period
            snapshot_type: Type of snapshot (PUNCTUAL or CUMULATIVE)
            jira_data: Raw data from Jira collector (optional)
            github_data: Raw data from GitHub collector (optional)
            preserved: Preserved fields from existing metrics (manual + optionally GitHub)

        Returns:
            MetricsDB instance ready to be added to session
        """
        # Extract Jira fields
        jira_fields = {}
        if jira_data:
            for key, (db_field, default) in cls.JIRA_FIELD_MAPPING.items():
                jira_fields[db_field] = jira_data.get(key, default)

        # Extract GitHub fields
        github_fields = {}
        if github_data:
            for key, (db_field, default) in cls.GITHUB_FIELD_MAPPING.items():
                github_fields[db_field] = github_data.get(key, default)

        return cls(
            project_id=project_id,
            period_start=period_start,
            period_end=period_end,
            period_year=period_end.year,
            period_month=period_end.month,
            snapshot_type=snapshot_type.value,
            **jira_fields,
            **github_fields,
            **(preserved or {}),
        )

    @staticmethod
    def build_metrics_dict(
        period_start: date,
        period_end: date,
        jira_data: dict | None = None,
        github_data: dict | None = None,
        preserved: dict | None = None,
    ) -> dict:
        """Build a metrics data dict from collector data.

        Used when you need a dict instead of a MetricsDB instance.

        Args:
            period_start: Start date for the metrics period
            period_end: End date for the metrics period
            jira_data: Raw data from Jira collector (optional)
            github_data: Raw data from GitHub collector (optional)
            preserved: Preserved fields from existing metrics

        Returns:
            Dict suitable for MetricsService.upsert_metrics
        """
        result = {
            "period_start": period_start,
            "period_end": period_end,
        }

        for mapping, source in (
            (MetricsDB.JIRA_FIELD_MAPPING, jira_data),
            (MetricsDB.GITHUB_FIELD_MAPPING, github_data),
        ):
            for key, (db_field, default) in mapping.items():
                result[db_field] = source.get(key, default) if source else None

        if preserved:
            result.update(preserved)

        return result
