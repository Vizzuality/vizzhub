"""Public interface for the scorecard module.

Other modules should import from here, never from scorecard internals.
"""

import structlog
from datetime import date
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.api.schemas.job import (
    CaptureHistoryRequest,
    JobDetailResponse,
    JobResponse,
    JobSummaryResponse,
)
from app.modules.scorecard.api.schemas.project import (
    PaginatedProjectsResponse,
    ProjectSummary,
)
from app.modules.scorecard.models.metrics import SnapshotType
from app.modules.scorecard.models.metrics.db import MetricsDB
from app.modules.scorecard.models.metrics.embedded import Milestone
from app.modules.scorecard.services.metrics_service import MetricsService

__all__ = [
    "CaptureHistoryRequest",
    "JobDetailResponse",
    "JobResponse",
    "JobSummaryResponse",
    "MetricsService",
    "Milestone",
    "PaginatedProjectsResponse",
    "ProjectSummary",
    "SnapshotType",
    "delete_project_metrics",
    "refresh_tracker_evm",
]

logger = structlog.get_logger()


def _resolve_budget(budget: float | None, project) -> float | None:
    if budget is not None:
        return budget
    return float(project.budget) if project.budget is not None else None


def _apply_evm_fields(metrics, budget: float | None, tracker_evm) -> None:
    """Set EVM fields on a metrics record from tracker data."""
    if budget is not None:
        metrics.budget_total = budget
    if tracker_evm.cost_to_date is not None:
        metrics.cost_to_date = tracker_evm.cost_to_date
    if tracker_evm.percent_completed is not None:
        metrics.percent_completed = tracker_evm.percent_completed
    if tracker_evm.percent_planned is not None:
        metrics.percent_planned = tracker_evm.percent_planned


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

    project = await db.get(ProjectDB, project_id)
    if not project:
        return

    effective_budget = _resolve_budget(budget, project)
    tracker_evm = await get_evm_from_tracker(
        project_id, db, project.start_date, project.end_date
    )

    today = date.today()
    year, month = today.year, today.month
    updated = False

    for snapshot_type in (SnapshotType.CUMULATIVE, SnapshotType.PUNCTUAL):
        metrics = await MetricsService.get_metrics(
            db, project_id, year, month, snapshot_type
        )
        if not metrics:
            continue
        _apply_evm_fields(metrics, effective_budget, tracker_evm)
        updated = True

    if updated:
        await db.flush()
        if score_cache:
            await score_cache.invalidate(str(project_id))


async def delete_project_metrics(db: AsyncSession, project_id: UUID) -> None:
    """Delete every metrics row for a project.

    Used by core when removing a project; keeps scorecard internals (MetricsDB)
    out of cross-module call sites.
    """
    await db.execute(delete(MetricsDB).where(MetricsDB.project_id == project_id))
