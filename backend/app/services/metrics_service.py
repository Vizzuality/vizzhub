"""Metrics service for creating and retrieving metrics with upsert behavior."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ScoringConfig
from app.models.metrics import MetricsDB, SnapshotType


class MetricsService:
    """Service for managing metrics with upsert behavior."""

    @staticmethod
    async def get_metrics(
        db: AsyncSession,
        project_id: str | UUID,
        year: int,
        month: int,
        snapshot_type: SnapshotType | None = None,
    ) -> MetricsDB | None:
        """Get metrics by project and period.

        Args:
            db: Database session
            project_id: Project UUID
            year: Period year
            month: Period month (1-12)
            snapshot_type: Optional filter by snapshot type

        Returns:
            MetricsDB if found, None otherwise
        """
        project_uuid = UUID(str(project_id)) if isinstance(project_id, str) else project_id

        query = (
            select(MetricsDB)
            .where(MetricsDB.project_id == project_uuid)
            .where(MetricsDB.period_year == year)
            .where(MetricsDB.period_month == month)
        )

        if snapshot_type is not None:
            query = query.where(MetricsDB.snapshot_type == snapshot_type.value)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_project_history(
        db: AsyncSession,
        project_id: str | UUID,
        snapshot_type: SnapshotType | None = None,
        limit: int = 12,
    ) -> list[MetricsDB]:
        """Get metrics history for a project.

        Args:
            db: Database session
            project_id: Project UUID
            snapshot_type: Optional filter by snapshot type
            limit: Maximum number of records to return

        Returns:
            List of MetricsDB ordered by period (most recent first)
        """
        project_uuid = UUID(str(project_id)) if isinstance(project_id, str) else project_id

        query = select(MetricsDB).where(MetricsDB.project_id == project_uuid)

        if snapshot_type is not None:
            query = query.where(MetricsDB.snapshot_type == snapshot_type.value)

        query = query.order_by(
            MetricsDB.period_year.desc(),
            MetricsDB.period_month.desc(),
        ).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def upsert_metrics(
        db: AsyncSession,
        project_id: str | UUID,
        year: int,
        month: int,
        snapshot_type: SnapshotType,
        config: ScoringConfig,
        data: dict,
    ) -> MetricsDB:
        """Create or update metrics for a specific period and type.

        If metrics exist for the same (project, year, month, type),
        they will be updated. Otherwise, a new record is created.

        Args:
            db: Database session
            project_id: Project UUID
            year: Period year
            month: Period month (1-12)
            snapshot_type: Type of snapshot (punctual or cumulative)
            config: Scoring configuration for weights/targets
            data: Metrics data dict

        Returns:
            Created or updated MetricsDB
        """
        project_uuid = UUID(str(project_id)) if isinstance(project_id, str) else project_id

        existing = await MetricsService.get_metrics(
            db, project_uuid, year, month, snapshot_type
        )

        # Remove fields that are set explicitly to avoid duplicate kwargs
        excluded_fields = {
            "project_id", "period_year", "period_month",
            "snapshot_type", "weights_applied", "targets_applied",
        }
        clean_data = {k: v for k, v in data.items() if k not in excluded_fields}

        if existing:
            # Update existing record
            for key, value in clean_data.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            existing.weights_applied = config.get_all_weights()
            existing.targets_applied = config.get_all_targets()
            await db.flush()
            await db.refresh(existing)
            return existing
        else:
            # Create new record
            metrics = MetricsDB(
                project_id=project_uuid,
                period_year=year,
                period_month=month,
                snapshot_type=snapshot_type.value,
                weights_applied=config.get_all_weights(),
                targets_applied=config.get_all_targets(),
                **clean_data,
            )
            db.add(metrics)
            await db.flush()
            await db.refresh(metrics)
            return metrics

    @staticmethod
    async def delete_metrics(
        db: AsyncSession,
        metrics_id: str | UUID,
    ) -> bool:
        """Delete metrics by ID.

        Args:
            db: Database session
            metrics_id: Metrics UUID

        Returns:
            True if deleted, False if not found
        """
        metrics_uuid = UUID(str(metrics_id)) if isinstance(metrics_id, str) else metrics_id

        result = await db.execute(
            select(MetricsDB).where(MetricsDB.id == metrics_uuid)
        )
        metrics = result.scalar_one_or_none()

        if not metrics:
            return False

        await db.delete(metrics)
        await db.flush()
        return True
