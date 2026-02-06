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
    async def get_latest_metrics_for_scoring(
        db: AsyncSession,
        project_id: str | UUID,
        snapshot_type: SnapshotType = SnapshotType.CUMULATIVE,
        limit: int = 20,
    ) -> list[MetricsDB]:
        """Get latest metrics ordered for score computation.

        Unlike get_project_history which orders by period, this orders by
        period_end and created_at to find the most recent data points for
        consolidation.

        Args:
            db: Database session
            project_id: Project UUID
            snapshot_type: Snapshot type filter
            limit: Maximum records to fetch

        Returns:
            List of MetricsDB ordered by period_end desc, created_at desc
        """
        project_uuid = UUID(str(project_id)) if isinstance(project_id, str) else project_id

        result = await db.execute(
            select(MetricsDB)
            .where(MetricsDB.project_id == project_uuid)
            .where(MetricsDB.snapshot_type == snapshot_type.value)
            .order_by(MetricsDB.period_end.desc(), MetricsDB.created_at.desc())
            .limit(limit)
        )
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
        sync_manual_fields: bool = True,
    ) -> MetricsDB:
        """Create or update metrics for a specific period and type.

        If metrics exist for the same (project, year, month, type),
        they will be updated. Otherwise, a new record is created.

        Manual fields (EVM, milestones, governance, etc.) are automatically
        synchronized to the other snapshot type for the same period.

        Args:
            db: Database session
            project_id: Project UUID
            year: Period year
            month: Period month (1-12)
            snapshot_type: Type of snapshot (punctual or cumulative)
            config: Scoring configuration for weights/targets
            data: Metrics data dict
            sync_manual_fields: If True, sync manual fields to other snapshot type

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
            result = existing
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
            result = metrics

        # Sync manual fields to the other snapshot type
        if sync_manual_fields:
            await MetricsService._sync_manual_fields_to_other_snapshot(
                db, project_uuid, year, month, snapshot_type, clean_data, config
            )

        return result

    @staticmethod
    async def _sync_manual_fields_to_other_snapshot(
        db: AsyncSession,
        project_id: UUID,
        year: int,
        month: int,
        source_snapshot_type: SnapshotType,
        data: dict,
        config: ScoringConfig,
    ) -> None:
        """Sync manual fields to the other snapshot type for the same period.

        This ensures that manual metrics (EVM, milestones, governance, etc.)
        are consistent across both PUNCTUAL and CUMULATIVE snapshots.

        Args:
            db: Database session
            project_id: Project UUID
            year: Period year
            month: Period month
            source_snapshot_type: The snapshot type that was just updated
            data: The data that was updated
            config: Scoring configuration
        """
        # Extract only manual fields from the data
        manual_fields_to_sync = {
            k: v for k, v in data.items()
            if k in MetricsDB.MANUAL_FIELDS and v is not None
        }

        if not manual_fields_to_sync:
            return

        # Determine the other snapshot type
        other_type = (
            SnapshotType.PUNCTUAL
            if source_snapshot_type == SnapshotType.CUMULATIVE
            else SnapshotType.CUMULATIVE
        )

        # Get the other snapshot if it exists
        other_snapshot = await MetricsService.get_metrics(
            db, project_id, year, month, other_type
        )

        if other_snapshot:
            # Update only the manual fields
            for key, value in manual_fields_to_sync.items():
                if hasattr(other_snapshot, key):
                    setattr(other_snapshot, key, value)
            await db.flush()

    @staticmethod
    def _fill_missing_fields_from_snapshots(
        preserved: dict,
        missing_fields: list[str],
        snapshots: list[MetricsDB],
    ) -> list[str]:
        """Fill missing fields from a list of snapshots.

        Args:
            preserved: Dict to update with found values
            missing_fields: List of field names still missing
            snapshots: List of MetricsDB snapshots to search

        Returns:
            Updated list of still-missing fields
        """
        for snapshot in snapshots:
            if not missing_fields:
                break
            for field in missing_fields[:]:
                value = getattr(snapshot, field, None)
                if value is not None:
                    preserved[field] = value
                    missing_fields.remove(field)
        return missing_fields

    @staticmethod
    def _partition_snapshots_by_period(
        snapshots: list[MetricsDB],
        target_year: int,
        target_month: int,
    ) -> tuple[list[MetricsDB], list[MetricsDB]]:
        """Partition snapshots into past and future relative to target period.

        Args:
            snapshots: List of all snapshots (ordered by period desc)
            target_year: Target period year
            target_month: Target period month

        Returns:
            Tuple of (past_snapshots, future_snapshots_ascending)
        """
        target_period = (target_year, target_month)
        past_snapshots = [
            s for s in snapshots
            if (s.period_year, s.period_month) < target_period
        ]
        future_snapshots = sorted(
            [s for s in snapshots if (s.period_year, s.period_month) > target_period],
            key=lambda s: (s.period_year, s.period_month)
        )
        return past_snapshots, future_snapshots

    @staticmethod
    async def get_manual_fields_for_historical_capture(
        db: AsyncSession,
        project_id: str | UUID,
        target_year: int,
        target_month: int,
    ) -> dict:
        """Get manual fields for historical capture with priority fallback.

        Priority order:
        1. Dashboard value (most recent metrics - what user sees/enters)
        2. Most recent past snapshot (before target month)
        3. Closest future snapshot (after target month)
        4. Default values if nothing exists

        Args:
            db: Database session
            project_id: Project UUID
            target_year: Target period year
            target_month: Target period month

        Returns:
            Dict of manual field names to values
        """
        project_uuid = UUID(str(project_id)) if isinstance(project_id, str) else project_id

        result = await db.execute(
            select(MetricsDB)
            .where(MetricsDB.project_id == project_uuid)
            .order_by(MetricsDB.period_year.desc(), MetricsDB.period_month.desc())
        )
        all_snapshots = list(result.scalars().all())

        if not all_snapshots:
            return MetricsDB.get_default_preserved_fields(include_github=False)

        dashboard = all_snapshots[0]
        preserved = dashboard.get_preserved_fields(include_github=False)

        missing_fields = [
            field for field in MetricsDB.MANUAL_FIELDS
            if preserved.get(field) is None
        ]

        if not missing_fields:
            return preserved

        past_snapshots, future_snapshots = MetricsService._partition_snapshots_by_period(
            all_snapshots, target_year, target_month
        )

        missing_fields = MetricsService._fill_missing_fields_from_snapshots(
            preserved, missing_fields, past_snapshots
        )
        MetricsService._fill_missing_fields_from_snapshots(
            preserved, missing_fields, future_snapshots
        )

        return preserved
