"""Snapshot service for creating and retrieving historical metric snapshots."""

import calendar
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.models.metrics import MetricsDB
from app.models.snapshot import MetricSnapshotDB


def _last_day_of_month(year: int, month: int) -> date:
    """Get the last day of a month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def _first_day_of_month(year: int, month: int) -> date:
    """Get the first day of a month."""
    return date(year, month, 1)


def _previous_month(year: int, month: int) -> tuple[int, int]:
    """Get the previous month as (year, month)."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


# All normalized fields in MetricsDB
NORMALIZED_FIELDS = [
    # EVM
    "budget_total", "cost_to_date", "percent_completed", "percent_planned",
    # Defects
    "bugs_total", "tasks_completed", "escaped_defects", "mttr_hours",
    "incidents_count", "post_contract_tasks",
    # Flow
    "lead_time_days", "lead_time_sample_size", "commitment_reliability",
    "committed_issues", "single_sprint_issues", "multi_sprint_issues",
    "total_stories", "stories_with_reviewer",
    # GitHub
    "prs_without_review", "total_merged_prs", "high_severity_vulns",
    "high_severity_vulns_total", "pr_size_median", "review_turnaround_hours",
    "deployment_frequency", "release_count_90d", "change_failure_rate",
    "total_releases", "failed_releases",
    # Manual
    "governance_exceptions", "strategic_impact",
]

# JSON fields in MetricsDB
JSON_FIELDS = [
    "milestones", "test_maturity", "architecture",
    "pm_satisfaction", "client_survey",
]

# Fields that require manual input (inherit from previous month if missing)
MANUAL_FIELDS = [
    "budget_total", "cost_to_date", "percent_completed", "percent_planned",
    "test_maturity", "architecture", "pm_satisfaction",
    "strategic_impact", "governance_exceptions",
]


class SnapshotService:
    """Service for managing metric snapshots."""

    @staticmethod
    async def create_snapshot(
        db: AsyncSession,
        project_id: str | UUID,
        year: int,
        month: int,
        config: ScoringConfig,
        snapshot_type: str = "monthly",
    ) -> MetricSnapshotDB:
        """Create a snapshot for a specific month.

        Process:
        1. Find latest metrics for the period
        2. Consolidate into a single metrics record
        3. Fill gaps from previous month's snapshot (if exists)
        4. Create snapshot pointing to consolidated metrics

        Args:
            db: Database session
            project_id: Project UUID
            year: Period year
            month: Period month (1-12)
            config: Scoring configuration
            snapshot_type: Type of snapshot (monthly, manual)

        Returns:
            Created MetricSnapshotDB

        Raises:
            ValueError: If no metrics found for the period
        """
        project_uuid = UUID(str(project_id)) if isinstance(project_id, str) else project_id

        period_start = _first_day_of_month(year, month)
        period_end = _last_day_of_month(year, month)

        result = await db.execute(
            select(MetricsDB)
            .where(MetricsDB.project_id == str(project_uuid))
            .where(MetricsDB.period_end >= period_start)
            .where(MetricsDB.period_end <= period_end)
            .order_by(MetricsDB.created_at.desc())
        )
        metrics_list = list(result.scalars().all())

        if not metrics_list:
            raise ValueError(f"No metrics found for {year}-{month:02d}")

        consolidated = await SnapshotService._create_consolidated_metrics(
            db, project_uuid, metrics_list, period_start, period_end, year, month
        )

        snapshot = MetricSnapshotDB(
            project_id=project_uuid,
            metrics_id=consolidated.id,
            period_year=year,
            period_month=month,
            snapshot_type=snapshot_type,
            weights_applied=config.get_all_weights(),
            targets_applied=config.get_all_targets(),
        )

        db.add(snapshot)
        await db.flush()
        await db.refresh(snapshot)

        return snapshot

    @staticmethod
    async def _create_consolidated_metrics(
        db: AsyncSession,
        project_id: UUID,
        metrics_list: list[MetricsDB],
        period_start: date,
        period_end: date,
        year: int,
        month: int,
    ) -> MetricsDB:
        """Create a consolidated metrics record from multiple sources.

        Takes the most recent non-null value for each field.
        Falls back to previous month's snapshot metrics for missing manual fields.
        """
        consolidated_data: dict = {
            "id": uuid4(),
            "project_id": str(project_id),
            "period_start": period_start,
            "period_end": period_end,
            "sev1_incident": False,
        }

        # Initialize all fields to None
        for field in NORMALIZED_FIELDS + JSON_FIELDS:
            consolidated_data[field] = None

        # Consolidate: take first non-null value from most recent metrics
        for field in NORMALIZED_FIELDS + JSON_FIELDS:
            for m in metrics_list:
                value = getattr(m, field)
                if value is not None:
                    consolidated_data[field] = value
                    break

        # Handle sev1_incident (True if any record has it)
        for m in metrics_list:
            if m.sev1_incident:
                consolidated_data["sev1_incident"] = True
                break

        # Fill missing manual fields from previous snapshot
        missing_manual = [f for f in MANUAL_FIELDS if consolidated_data.get(f) is None]

        if missing_manual:
            prev_year, prev_month = _previous_month(year, month)
            prev_snapshot = await SnapshotService.get_snapshot(db, project_id, prev_year, prev_month)

            if prev_snapshot:
                prev_metrics_result = await db.execute(
                    select(MetricsDB).where(MetricsDB.id == prev_snapshot.metrics_id)
                )
                prev_metrics = prev_metrics_result.scalar_one_or_none()

                if prev_metrics:
                    for field in missing_manual:
                        if consolidated_data.get(field) is None:
                            prev_value = getattr(prev_metrics, field)
                            if prev_value is not None:
                                consolidated_data[field] = prev_value

        consolidated = MetricsDB(**consolidated_data)
        db.add(consolidated)
        await db.flush()

        return consolidated

    @staticmethod
    async def get_snapshot(
        db: AsyncSession,
        project_id: str | UUID,
        year: int,
        month: int,
    ) -> MetricSnapshotDB | None:
        """Get a specific snapshot by project and period.

        Args:
            db: Database session
            project_id: Project UUID
            year: Period year
            month: Period month (1-12)

        Returns:
            MetricSnapshotDB if found, None otherwise
        """
        project_uuid = UUID(str(project_id)) if isinstance(project_id, str) else project_id

        result = await db.execute(
            select(MetricSnapshotDB)
            .where(MetricSnapshotDB.project_id == project_uuid)
            .where(MetricSnapshotDB.period_year == year)
            .where(MetricSnapshotDB.period_month == month)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_project_history(
        db: AsyncSession,
        project_id: str | UUID,
        limit: int = 12,
    ) -> list[MetricSnapshotDB]:
        """Get snapshot history for a project.

        Args:
            db: Database session
            project_id: Project UUID
            limit: Maximum number of snapshots to return

        Returns:
            List of MetricSnapshotDB ordered by period (most recent first)
        """
        project_uuid = UUID(str(project_id)) if isinstance(project_id, str) else project_id

        result = await db.execute(
            select(MetricSnapshotDB)
            .where(MetricSnapshotDB.project_id == project_uuid)
            .order_by(
                MetricSnapshotDB.period_year.desc(),
                MetricSnapshotDB.period_month.desc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def delete_snapshot(
        db: AsyncSession,
        snapshot_id: str | UUID,
    ) -> bool:
        """Delete a snapshot and its consolidated metrics.

        Args:
            db: Database session
            snapshot_id: Snapshot UUID

        Returns:
            True if deleted, False if not found
        """
        snapshot_uuid = UUID(str(snapshot_id)) if isinstance(snapshot_id, str) else snapshot_id

        result = await db.execute(
            select(MetricSnapshotDB).where(MetricSnapshotDB.id == snapshot_uuid)
        )
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            return False

        metrics_result = await db.execute(
            select(MetricsDB).where(MetricsDB.id == snapshot.metrics_id)
        )
        metrics = metrics_result.scalar_one_or_none()

        await db.delete(snapshot)
        if metrics:
            await db.delete(metrics)

        await db.flush()
        return True
