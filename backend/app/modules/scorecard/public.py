"""Public interface for the scorecard module.

Other modules should import from here, never from scorecard internals.
"""

import logging
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.models.metrics import SnapshotType
from app.modules.scorecard.models.metrics.embedded import Milestone
from app.modules.scorecard.services.metrics_service import MetricsService

__all__ = ["MetricsService", "Milestone", "SnapshotType", "refresh_tracker_evm"]

logger = logging.getLogger(__name__)


async def refresh_tracker_evm(
    db: AsyncSession,
    project_id: UUID,
    budget: float | None = None,
    score_cache=None,
) -> None:
    """Refresh EVM fields on current-period metrics from tracker data.

    Updates budget_total, cost_to_date, percent_completed, percent_planned
    on both cumulative and punctual snapshots without re-collecting from
    Jira/GitHub. Invalidates score cache afterwards.
    """
    from app.core.models.project import ProjectDB
    from app.modules.tracker.public import get_evm_from_tracker

    today = date.today()
    year, month = today.year, today.month

    project = await db.get(ProjectDB, project_id)
    if not project:
        return

    effective_budget = budget if budget is not None else (
        float(project.budget) if project.budget is not None else None
    )

    tracker_evm = await get_evm_from_tracker(
        project_id, db, project.start_date, project.end_date
    )

    has_metrics = False
    for snapshot_type in (SnapshotType.CUMULATIVE, SnapshotType.PUNCTUAL):
        metrics = await MetricsService.get_metrics(
            db, project_id, year, month, snapshot_type
        )
        if not metrics:
            continue
        has_metrics = True

        if effective_budget is not None:
            metrics.budget_total = effective_budget
        if tracker_evm.cost_to_date is not None:
            metrics.cost_to_date = tracker_evm.cost_to_date
        if tracker_evm.percent_completed is not None:
            metrics.percent_completed = tracker_evm.percent_completed
        if tracker_evm.percent_planned is not None:
            metrics.percent_planned = tracker_evm.percent_planned

    if has_metrics:
        await db.flush()
        if score_cache:
            await score_cache.invalidate(str(project_id))
