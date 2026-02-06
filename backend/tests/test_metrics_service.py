"""Tests for metrics service with upsert behavior.

These tests verify:
1. Only ONE punctual metrics record allowed per project per month
2. Only ONE cumulative metrics record allowed per project per month
3. Both types CAN coexist for the same month
4. Upsert behavior replaces existing for same type
5. History retrieval with optional type filtering
"""

import pytest
import pytest_asyncio
from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.models.metrics import MetricsDB, SnapshotType
from app.models.project import ProjectDB
from app.services.metrics_service import MetricsService


@pytest_asyncio.fixture
async def test_project(db_session: AsyncSession) -> ProjectDB:
    """Create a test project for metrics tests."""
    project = ProjectDB(
        id=str(uuid4()),
        name="Metrics Test Project",
        jira_project_key="METR",
        github_repo="test/metrics-test",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        status="in_progress",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


class TestMetricsServiceGetMetrics:
    """Tests for MetricsService.get_metrics."""

    @pytest.mark.asyncio
    async def test_get_metrics_not_exists(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Test getting non-existent metrics returns None."""
        result = await MetricsService.get_metrics(
            db_session, test_project.id, 2024, 6
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_metrics_with_type_filter(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test get_metrics with type filter only returns matching type."""
        await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {"period_start": date(2024, 1, 1), "period_end": date(2024, 1, 31)},
        )

        found_punctual = await MetricsService.get_metrics(
            db_session, test_project.id, 2024, 1, SnapshotType.PUNCTUAL
        )
        found_cumulative = await MetricsService.get_metrics(
            db_session, test_project.id, 2024, 1, SnapshotType.CUMULATIVE
        )

        assert found_punctual is not None
        assert found_cumulative is None


class TestMetricsServiceUpsert:
    """Tests for MetricsService.upsert_metrics."""

    @pytest.mark.asyncio
    async def test_upsert_creates_new_record(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test upsert creates new record when none exists."""
        metrics = await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {
                "period_start": date(2024, 1, 1),
                "period_end": date(2024, 1, 31),
                "bugs_total": 10,
                "tasks_completed": 50,
            },
        )

        assert metrics is not None
        assert metrics.project_id == test_project.id
        assert metrics.period_year == 2024
        assert metrics.period_month == 1
        assert metrics.snapshot_type == "punctual"
        assert metrics.bugs_total == 10
        assert metrics.tasks_completed == 50
        assert metrics.weights_applied is not None
        assert metrics.targets_applied is not None

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_record(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test upsert updates existing record instead of creating new."""
        first = await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {
                "period_start": date(2024, 1, 1),
                "period_end": date(2024, 1, 31),
                "bugs_total": 10,
            },
        )
        first_id = first.id

        updated = await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {
                "period_start": date(2024, 1, 1),
                "period_end": date(2024, 1, 31),
                "bugs_total": 20,
            },
        )

        assert updated.id == first_id
        assert updated.bugs_total == 20

    @pytest.mark.asyncio
    async def test_upsert_preserves_unset_fields(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test upsert doesn't overwrite fields not in data dict."""
        await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {
                "period_start": date(2024, 1, 1),
                "period_end": date(2024, 1, 31),
                "bugs_total": 10,
                "tasks_completed": 50,
            },
        )

        updated = await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {
                "period_start": date(2024, 1, 1),
                "period_end": date(2024, 1, 31),
                "bugs_total": 20,
            },
        )

        assert updated.bugs_total == 20
        assert updated.tasks_completed == 50


class TestMetricsTypeUniqueness:
    """Tests for metrics type uniqueness rules."""

    @pytest.mark.asyncio
    async def test_allows_both_types_same_month(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Can have one punctual AND one cumulative for same month."""
        punctual = await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {"period_start": date(2024, 1, 1), "period_end": date(2024, 1, 31)},
        )

        cumulative = await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.CUMULATIVE,
            scoring_config,
            {"period_start": date(2024, 1, 1), "period_end": date(2024, 1, 31)},
        )

        assert punctual is not None
        assert cumulative is not None
        assert punctual.id != cumulative.id
        assert punctual.snapshot_type == "punctual"
        assert cumulative.snapshot_type == "cumulative"

    @pytest.mark.asyncio
    async def test_upsert_does_not_affect_other_type(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Updating punctual does not affect cumulative."""
        await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {"period_start": date(2024, 1, 1), "period_end": date(2024, 1, 31)},
        )
        cumulative = await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.CUMULATIVE,
            scoring_config,
            {"period_start": date(2024, 1, 1), "period_end": date(2024, 1, 31)},
        )
        cumulative_id = cumulative.id

        await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {
                "period_start": date(2024, 1, 1),
                "period_end": date(2024, 1, 31),
                "bugs_total": 99,
            },
        )

        cumulative_still_exists = await db_session.execute(
            select(MetricsDB).where(MetricsDB.id == cumulative_id)
        )
        found = cumulative_still_exists.scalar_one_or_none()
        assert found is not None
        assert found.bugs_total is None


class TestMetricsServiceHistory:
    """Tests for MetricsService.get_project_history."""

    @pytest.mark.asyncio
    async def test_get_history_empty(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
    ) -> None:
        """Test getting history with no metrics."""
        history = await MetricsService.get_project_history(
            db_session, test_project.id
        )
        assert history == []

    @pytest.mark.asyncio
    async def test_get_history_single_record(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test getting history with one metrics record."""
        await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {"period_start": date(2024, 1, 1), "period_end": date(2024, 1, 31)},
        )

        history = await MetricsService.get_project_history(
            db_session, test_project.id
        )
        assert len(history) == 1
        assert history[0].period_year == 2024
        assert history[0].period_month == 1

    @pytest.mark.asyncio
    async def test_get_history_respects_limit(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test that history respects the limit parameter."""
        for month in range(1, 4):
            await MetricsService.upsert_metrics(
                db_session,
                test_project.id,
                2024,
                month,
                SnapshotType.PUNCTUAL,
                scoring_config,
                {
                    "period_start": date(2024, month, 1),
                    "period_end": date(2024, month, 28),
                },
            )

        history = await MetricsService.get_project_history(
            db_session, test_project.id, limit=2
        )
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_history_ordered_by_period_desc(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test that history is ordered by period descending."""
        for month in [1, 3, 2]:
            await MetricsService.upsert_metrics(
                db_session,
                test_project.id,
                2024,
                month,
                SnapshotType.PUNCTUAL,
                scoring_config,
                {
                    "period_start": date(2024, month, 1),
                    "period_end": date(2024, month, 28),
                },
            )

        history = await MetricsService.get_project_history(
            db_session, test_project.id
        )

        assert len(history) == 3
        assert history[0].period_month == 3
        assert history[1].period_month == 2
        assert history[2].period_month == 1

    @pytest.mark.asyncio
    async def test_get_history_filters_by_snapshot_type(
        self,
        db_session: AsyncSession,
        test_project: ProjectDB,
        scoring_config: ScoringConfig,
    ) -> None:
        """Test that history can filter by snapshot type."""
        await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.PUNCTUAL,
            scoring_config,
            {"period_start": date(2024, 1, 1), "period_end": date(2024, 1, 31)},
        )
        await MetricsService.upsert_metrics(
            db_session,
            test_project.id,
            2024,
            1,
            SnapshotType.CUMULATIVE,
            scoring_config,
            {"period_start": date(2024, 1, 1), "period_end": date(2024, 1, 31)},
        )

        punctual_only = await MetricsService.get_project_history(
            db_session, test_project.id, snapshot_type=SnapshotType.PUNCTUAL
        )
        cumulative_only = await MetricsService.get_project_history(
            db_session, test_project.id, snapshot_type=SnapshotType.CUMULATIVE
        )
        all_types = await MetricsService.get_project_history(
            db_session, test_project.id
        )

        assert len(punctual_only) == 1
        assert punctual_only[0].snapshot_type == "punctual"
        assert len(cumulative_only) == 1
        assert cumulative_only[0].snapshot_type == "cumulative"
        assert len(all_types) == 2


class TestSnapshotTypeEnum:
    """Tests for SnapshotType enum."""

    def test_snapshot_type_values(self) -> None:
        """SnapshotType enum has correct values."""
        assert SnapshotType.PUNCTUAL.value == "punctual"
        assert SnapshotType.CUMULATIVE.value == "cumulative"
        assert len(SnapshotType) == 2
