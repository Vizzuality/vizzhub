"""Score computation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import inspect

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, get_project_or_404, limiter
from app.core.exceptions import MetricsNotFoundError
from app.models.indicators import IndicatorsCreate
from app.models.metrics import MetricsCreate, MetricsDB, SnapshotType
from app.models.scores import FinalScore
from app.services.metrics_service import MetricsService
from app.services.score_computation import ScoreComputationService

router = APIRouter()

# Fields excluded from consolidation (metadata, not metrics data)
_CONSOLIDATION_EXCLUDE_FIELDS = frozenset({
    "id",
    "project_id",
    "period_start",
    "period_end",
    "period_year",
    "period_month",
    "snapshot_type",
    "weights_applied",
    "targets_applied",
    "created_at",
    "sev1_incident",  # Handled separately with OR logic
})


def _get_consolidation_fields() -> list[str]:
    """Get list of MetricsDB fields that should be consolidated.

    Uses SQLAlchemy introspection to automatically include all metric columns,
    excluding metadata fields. This ensures new columns are automatically included.
    """
    mapper = inspect(MetricsDB)
    return [
        col.key for col in mapper.columns
        if col.key not in _CONSOLIDATION_EXCLUDE_FIELDS
    ]


class ScoreRequest(BaseModel):
    """Request body for ad-hoc score calculation."""

    metrics: MetricsCreate
    sev1_incident: bool = False


class ScoreResponse(BaseModel):
    """Response with calculated scores."""

    indicators: IndicatorsCreate
    scores: FinalScore


@router.post("/calculate")
@limiter.limit("30/minute")
async def calculate_scores(
    request: Request,
    score_request: ScoreRequest,
    current_user: CurrentUser,
    config: ScoringConfigDep,
) -> ScoreResponse:
    """Calculate scores from provided metrics (ad-hoc, not stored)."""
    score_service = ScoreComputationService(config)
    indicators, scores = score_service.compute(
        score_request.metrics,
        sev1_incident=score_request.sev1_incident,
    )
    return ScoreResponse(indicators=indicators, scores=scores)


@router.get("/project/{project_id}")
@limiter.limit("100/minute")
async def get_project_scores(
    request: Request,
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    snapshot_type: SnapshotType = SnapshotType.CUMULATIVE,
    year: int | None = None,
    month: int | None = None,
) -> ScoreResponse:
    """Calculate scores from a project's metrics.

    Args:
        snapshot_type: Filter by snapshot type (default: cumulative)
        year: Optional year filter (requires month)
        month: Optional month filter (requires year)

    When year and month are provided, returns scores for that specific period.
    Otherwise, returns scores for the latest metrics.

    Since collectors create separate records, this endpoint consolidates
    metrics from the same period_end date, taking the most recent non-null
    value for each field.
    """
    await get_project_or_404(db, project_id)

    if year is not None and month is not None:
        metrics_db = await MetricsService.get_metrics(
            db, project_id, year, month, snapshot_type
        )
        if not metrics_db:
            raise MetricsNotFoundError(str(project_id))
    else:
        metrics_list = await MetricsService.get_latest_metrics_for_scoring(
            db, project_id, snapshot_type
        )
        if not metrics_list:
            raise MetricsNotFoundError(str(project_id))

        latest_period_end = metrics_list[0].period_end
        same_period = [m for m in metrics_list if m.period_end == latest_period_end]
        metrics_db = _consolidate_metrics(same_period)

    metrics = MetricsCreate.from_db(metrics_db)

    score_service = ScoreComputationService(config)
    indicators, scores = score_service.compute(metrics, sev1_incident=metrics_db.sev1_incident)

    return ScoreResponse(indicators=indicators, scores=scores)


def _consolidate_metrics(metrics_list: list[MetricsDB]) -> MetricsDB:
    """Consolidate multiple metrics records, taking first non-null value for each field.

    Uses SQLAlchemy introspection to automatically discover fields, ensuring new
    columns added to MetricsDB are automatically included in consolidation.
    """
    if len(metrics_list) == 1:
        return metrics_list[0]

    base = metrics_list[0]

    # Consolidate all metric fields (discovered via introspection)
    for field in _get_consolidation_fields():
        if getattr(base, field) is None:
            for m in metrics_list[1:]:
                value = getattr(m, field)
                if value is not None:
                    setattr(base, field, value)
                    break

    # sev1_incident uses OR logic: true if any record has it true
    if not base.sev1_incident:
        base.sev1_incident = any(m.sev1_incident for m in metrics_list[1:])

    return base


@router.get("/project/{project_id}/history")
async def get_project_score_history(
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    snapshot_type: SnapshotType = SnapshotType.CUMULATIVE,
    limit: int = 10,
) -> list[ScoreResponse]:
    """Get score history for a project.

    Args:
        snapshot_type: Filter by snapshot type (default: cumulative)
    """
    await get_project_or_404(db, project_id)

    metrics_list = await MetricsService.get_latest_metrics_for_scoring(
        db, project_id, snapshot_type, limit
    )

    score_service = ScoreComputationService(config)
    responses = []
    for metrics_db in metrics_list:
        metrics = MetricsCreate.from_db(metrics_db)
        indicators, scores = score_service.compute(metrics, sev1_incident=metrics_db.sev1_incident)
        responses.append(ScoreResponse(indicators=indicators, scores=scores))

    return responses
