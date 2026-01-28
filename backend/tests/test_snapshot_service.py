"""Tests for snapshot service."""

import pytest
import pytest_asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.models.metrics import MetricsDB
from app.models.project import ProjectDB
from app.models.snapshot import MetricSnapshotDB
from app.services.snapshot_service import (
    SnapshotService,
    _last_day_of_month,
    _first_day_of_month,
    _previous_month,
)


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_last_day_of_month_january(self) -> None:
        result = _last_day_of_month(2024, 1)
        assert result == date(2024, 1, 31)

    def test_last_day_of_month_february_leap_year(self) -> None:
        result = _last_day_of_month(2024, 2)
        assert result == date(2024, 2, 29)

    def test_last_day_of_month_february_non_leap(self) -> None:
        result = _last_day_of_month(2023, 2)
        assert result == date(2023, 2, 28)

    def test_last_day_of_month_december(self) -> None:
        result = _last_day_of_month(2024, 12)
        assert result == date(2024, 12, 31)

    def test_first_day_of_month(self) -> None:
        result = _first_day_of_month(2024, 6)
        assert result == date(2024, 6, 1)

    def test_previous_month_middle_of_year(self) -> None:
        year, month = _previous_month(2024, 6)
        assert year == 2024
        assert month == 5

    def test_previous_month_january(self) -> None:
        year, month = _previous_month(2024, 1)
        assert year == 2023
        assert month == 12


@pytest_asyncio.fixture
async def snapshot_project(db_session: AsyncSession) -> ProjectDB:
    """Create a test project for snapshot tests."""
    project = ProjectDB(
        id=str(uuid4()),
        name="Snapshot Test Project",
        jira_project_key="SNAP",
        github_repo="test/snapshot-test",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        status="in_progress",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def january_metrics(
    db_session: AsyncSession, snapshot_project: ProjectDB
) -> MetricsDB:
    """Create metrics for January 2024."""
    metrics = MetricsDB(
        project_id=str(snapshot_project.id),
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 15),
        budget_total=Decimal("100000.0"),
        cost_to_date=Decimal("25000.0"),
        percent_completed=Decimal("0.25"),
        percent_planned=Decimal("0.25"),
        bugs_total=10,
        tasks_completed=50,
        escaped_defects=2,
        total_merged_prs=20,
        prs_without_review=2,
        test_maturity={"e2e": 3, "unit": 4},
    )
    db_session.add(metrics)
    await db_session.commit()
    await db_session.refresh(metrics)
    return metrics


@pytest_asyncio.fixture
async def multiple_january_metrics(
    db_session: AsyncSession, snapshot_project: ProjectDB
) -> list[MetricsDB]:
    """Create multiple metrics records for January 2024."""
    metrics1 = MetricsDB(
        project_id=str(snapshot_project.id),
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 10),
        bugs_total=5,
        tasks_completed=30,
    )
    metrics2 = MetricsDB(
        project_id=str(snapshot_project.id),
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 20),
        total_merged_prs=15,
        prs_without_review=1,
        budget_total=Decimal("100000.0"),
        cost_to_date=Decimal("20000.0"),
    )
    db_session.add(metrics1)
    db_session.add(metrics2)
    await db_session.commit()
    return [metrics1, metrics2]


class TestSnapshotServiceCreateSnapshot:
    """Tests for SnapshotService.create_snapshot."""

    @pytest.mark.asyncio
    async def test_create_snapshot_success(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        january_metrics: MetricsDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test creating a snapshot with valid metrics."""
        snapshot = await SnapshotService.create_snapshot(
            db_session,
            snapshot_project.id,
            2024,
            1,
            scoring_config,
        )

        assert snapshot is not None
        assert snapshot.project_id == snapshot_project.id
        assert snapshot.period_year == 2024
        assert snapshot.period_month == 1
        assert snapshot.snapshot_type == "monthly"
        assert snapshot.metrics_id is not None
        assert snapshot.weights_applied is not None
        assert snapshot.targets_applied is not None

    @pytest.mark.asyncio
    async def test_create_snapshot_no_metrics_raises(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test that creating a snapshot without metrics raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await SnapshotService.create_snapshot(
                db_session,
                snapshot_project.id,
                2024,
                6,
                scoring_config,
            )
        assert "No metrics found for 2024-06" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_snapshot_consolidates_multiple_metrics(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        multiple_january_metrics: list[MetricsDB],
        scoring_config: ScoringConfig,
    ) -> None:
        """Test that multiple metrics are consolidated into one."""
        snapshot = await SnapshotService.create_snapshot(
            db_session,
            snapshot_project.id,
            2024,
            1,
            scoring_config,
        )

        result = await db_session.execute(
            select(MetricsDB).where(MetricsDB.id == snapshot.metrics_id)
        )
        consolidated = result.scalar_one()

        assert consolidated.bugs_total == 5
        assert consolidated.tasks_completed == 30
        assert consolidated.total_merged_prs == 15
        assert consolidated.prs_without_review == 1
        assert consolidated.budget_total == Decimal("100000.0")

    @pytest.mark.asyncio
    async def test_create_snapshot_with_string_project_id(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        january_metrics: MetricsDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test creating snapshot with string project_id."""
        snapshot = await SnapshotService.create_snapshot(
            db_session,
            str(snapshot_project.id),
            2024,
            1,
            scoring_config,
        )
        assert snapshot is not None
        assert snapshot.project_id == snapshot_project.id

    @pytest.mark.asyncio
    async def test_create_snapshot_custom_type(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        january_metrics: MetricsDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test creating a manual snapshot."""
        snapshot = await SnapshotService.create_snapshot(
            db_session,
            snapshot_project.id,
            2024,
            1,
            scoring_config,
            snapshot_type="manual",
        )
        assert snapshot.snapshot_type == "manual"


class TestSnapshotServiceGetSnapshot:
    """Tests for SnapshotService.get_snapshot."""

    @pytest.mark.asyncio
    async def test_get_snapshot_exists(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        january_metrics: MetricsDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test getting an existing snapshot."""
        created = await SnapshotService.create_snapshot(
            db_session, snapshot_project.id, 2024, 1, scoring_config
        )

        found = await SnapshotService.get_snapshot(
            db_session, snapshot_project.id, 2024, 1
        )

        assert found is not None
        assert found.id == created.id

    @pytest.mark.asyncio
    async def test_get_snapshot_not_exists(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
    ) -> None:
        """Test getting a non-existent snapshot returns None."""
        result = await SnapshotService.get_snapshot(
            db_session, snapshot_project.id, 2024, 6
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_snapshot_with_string_project_id(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        january_metrics: MetricsDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test getting snapshot with string project_id."""
        await SnapshotService.create_snapshot(
            db_session, snapshot_project.id, 2024, 1, scoring_config
        )

        found = await SnapshotService.get_snapshot(
            db_session, str(snapshot_project.id), 2024, 1
        )
        assert found is not None


class TestSnapshotServiceGetProjectHistory:
    """Tests for SnapshotService.get_project_history."""

    @pytest.mark.asyncio
    async def test_get_history_empty(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
    ) -> None:
        """Test getting history with no snapshots."""
        history = await SnapshotService.get_project_history(
            db_session, snapshot_project.id
        )
        assert history == []

    @pytest.mark.asyncio
    async def test_get_history_single_snapshot(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        january_metrics: MetricsDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test getting history with one snapshot."""
        await SnapshotService.create_snapshot(
            db_session, snapshot_project.id, 2024, 1, scoring_config
        )

        history = await SnapshotService.get_project_history(
            db_session, snapshot_project.id
        )
        assert len(history) == 1
        assert history[0].period_year == 2024
        assert history[0].period_month == 1

    @pytest.mark.asyncio
    async def test_get_history_respects_limit(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test that history respects the limit parameter."""
        for month in range(1, 4):
            metrics = MetricsDB(
                project_id=str(snapshot_project.id),
                period_start=date(2024, month, 1),
                period_end=date(2024, month, 15),
                bugs_total=10,
                tasks_completed=50,
            )
            db_session.add(metrics)
            await db_session.commit()

            await SnapshotService.create_snapshot(
                db_session, snapshot_project.id, 2024, month, scoring_config
            )

        history = await SnapshotService.get_project_history(
            db_session, snapshot_project.id, limit=2
        )
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_history_ordered_by_period_desc(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test that history is ordered by period descending."""
        for month in [1, 3, 2]:
            metrics = MetricsDB(
                project_id=str(snapshot_project.id),
                period_start=date(2024, month, 1),
                period_end=date(2024, month, 15),
                bugs_total=10,
                tasks_completed=50,
            )
            db_session.add(metrics)
            await db_session.commit()

            await SnapshotService.create_snapshot(
                db_session, snapshot_project.id, 2024, month, scoring_config
            )

        history = await SnapshotService.get_project_history(
            db_session, snapshot_project.id
        )

        assert len(history) == 3
        assert history[0].period_month == 3
        assert history[1].period_month == 2
        assert history[2].period_month == 1


class TestSnapshotServiceDeleteSnapshot:
    """Tests for SnapshotService.delete_snapshot."""

    @pytest.mark.asyncio
    async def test_delete_snapshot_success(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        january_metrics: MetricsDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test deleting an existing snapshot."""
        snapshot = await SnapshotService.create_snapshot(
            db_session, snapshot_project.id, 2024, 1, scoring_config
        )
        snapshot_id = snapshot.id
        metrics_id = snapshot.metrics_id

        result = await SnapshotService.delete_snapshot(db_session, snapshot_id)
        assert result is True

        found = await db_session.execute(
            select(MetricSnapshotDB).where(MetricSnapshotDB.id == snapshot_id)
        )
        assert found.scalar_one_or_none() is None

        found_metrics = await db_session.execute(
            select(MetricsDB).where(MetricsDB.id == metrics_id)
        )
        assert found_metrics.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_snapshot_not_found(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test deleting a non-existent snapshot returns False."""
        result = await SnapshotService.delete_snapshot(db_session, uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_snapshot_with_string_id(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        january_metrics: MetricsDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test deleting snapshot with string ID."""
        snapshot = await SnapshotService.create_snapshot(
            db_session, snapshot_project.id, 2024, 1, scoring_config
        )

        result = await SnapshotService.delete_snapshot(db_session, str(snapshot.id))
        assert result is True


class TestSnapshotInheritance:
    """Tests for inheriting manual fields from previous snapshots."""

    @pytest.mark.asyncio
    async def test_inherits_from_previous_snapshot(
        self,
        db_session: AsyncSession,
        snapshot_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test that manual fields are inherited from previous month."""
        jan_metrics = MetricsDB(
            project_id=str(snapshot_project.id),
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 15),
            budget_total=Decimal("100000.0"),
            cost_to_date=Decimal("25000.0"),
            percent_completed=Decimal("0.25"),
            percent_planned=Decimal("0.25"),
            bugs_total=10,
            tasks_completed=50,
            test_maturity={"e2e": 4, "unit": 5},
        )
        db_session.add(jan_metrics)
        await db_session.commit()

        jan_snapshot = await SnapshotService.create_snapshot(
            db_session, snapshot_project.id, 2024, 1, scoring_config
        )

        feb_metrics = MetricsDB(
            project_id=str(snapshot_project.id),
            period_start=date(2024, 2, 1),
            period_end=date(2024, 2, 15),
            bugs_total=8,
            tasks_completed=60,
        )
        db_session.add(feb_metrics)
        await db_session.commit()

        feb_snapshot = await SnapshotService.create_snapshot(
            db_session, snapshot_project.id, 2024, 2, scoring_config
        )

        result = await db_session.execute(
            select(MetricsDB).where(MetricsDB.id == feb_snapshot.metrics_id)
        )
        feb_consolidated = result.scalar_one()

        assert feb_consolidated.budget_total == Decimal("100000.0")
        assert feb_consolidated.cost_to_date == Decimal("25000.0")
        assert feb_consolidated.test_maturity == {"e2e": 4, "unit": 5}
