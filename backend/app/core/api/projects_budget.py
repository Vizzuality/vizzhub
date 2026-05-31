"""Project budget + milestones endpoint (/api/projects/{project_id}/budget)."""

import calendar
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import get_scoring_config
from app.core.api.deps import (
    CurrentUser,
    DBSession,
    OptionalScoreCache,
    get_project_or_404,
    limiter,
)
from app.modules.scorecard.public import (
    MetricsService,
    Milestone,
    SnapshotType,
    refresh_tracker_evm,
)

router = APIRouter()


class ProjectBudgetUpdate(BaseModel):
    milestones: list[Milestone] | None = None


def _metrics_to_budget_response(metrics: Any, year: int, month: int) -> dict:
    """Build budget response from a scorecard metrics record."""
    milestones = metrics.milestones if metrics.milestones else []
    return {
        "period_year": year,
        "period_month": month,
        "milestones": milestones,
    }


@router.put("/{project_id}/budget")
@limiter.limit("60/minute")
async def update_project_budget(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    project_id: UUID,
    payload: ProjectBudgetUpdate,
    cache: OptionalScoreCache,
) -> dict:
    """Update milestones and budget_total for current period.

    EVM fields (cost_to_date, percent_completed, percent_planned) are now
    derived from the tracker module, not manually entered.
    """
    project = await get_project_or_404(db, project_id)

    today = date.today()
    year, month = today.year, today.month
    config = get_scoring_config()

    data: dict = {
        "period_start": date(year, month, 1),
        "period_end": date(year, month, calendar.monthrange(year, month)[1]),
    }
    if project.budget is not None:
        data["budget_total"] = float(project.budget)
    if payload.milestones is not None:
        data["milestones"] = [m.model_dump(mode="json") for m in payload.milestones]

    has_budget_data = any(k not in ("period_start", "period_end") for k in data)
    if not has_budget_data:
        existing = await MetricsService.get_metrics(db, str(project_id), year, month)
        if existing:
            return _metrics_to_budget_response(existing, year, month)
        return {"period_year": year, "period_month": month, "milestones": []}

    metrics = await MetricsService.upsert_metrics(
        db, project_id, year, month, SnapshotType.CUMULATIVE, config, data
    )

    await refresh_tracker_evm(db, project_id, score_cache=cache)

    return _metrics_to_budget_response(metrics, year, month)
