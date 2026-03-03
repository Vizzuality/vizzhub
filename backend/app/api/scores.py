"""Score computation endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import inspect

from app.core.api.deps import (
    CurrentUser,
    DBSession,
    OptionalScoreCache,
    ScoringConfigDep,
    get_project_or_404,
    limiter,
)
from app.core.exceptions import MetricsNotFoundError
from app.models.indicators import IndicatorsCreate
from app.models.metrics import MetricsCreate, MetricsDB, SnapshotType
from app.models.scores import FinalScore
from app.services.metrics_service import MetricsService
from app.services.score_computation import ScoreComputationService

logger = logging.getLogger(__name__)

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


class BatchScoresRequest(BaseModel):
    """Request body for batch score retrieval."""

    project_ids: list[str] = Field(..., min_length=1, max_length=50)
    snapshot_type: SnapshotType = SnapshotType.CUMULATIVE


class BatchScoresResponse(BaseModel):
    """Response for batch score retrieval."""

    scores: dict[str, ScoreResponse]
    errors: dict[str, str]


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
    cache: OptionalScoreCache,
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
    # Cache lookup only for "latest" queries (no specific period)
    is_latest = year is None and month is None
    if is_latest and cache:
        cached = await cache.get(str(project_id), snapshot_type.value)
        if cached:
            return ScoreResponse(**cached)

    await get_project_or_404(db, project_id)

    if year is not None and month is not None:
        metrics_db = await MetricsService.get_metrics(
            db, project_id, year, month, snapshot_type
        )
        if not metrics_db:
            raise MetricsNotFoundError(str(project_id))

        metrics = MetricsCreate.from_db(metrics_db)
        score_service = ScoreComputationService(config)
        indicators, scores = score_service.compute(metrics, sev1_incident=metrics_db.sev1_incident)
        return ScoreResponse(indicators=indicators, scores=scores)

    response = await _compute_latest_scores(db, project_id, snapshot_type, config)
    if response is None:
        raise MetricsNotFoundError(str(project_id))

    if cache:
        await cache.set(str(project_id), response.model_dump(), snapshot_type.value)

    return response


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


async def _compute_latest_scores(
    db: DBSession,
    project_id: UUID,
    snapshot_type: SnapshotType,
    config: ScoringConfigDep,
) -> ScoreResponse | None:
    """Fetch latest metrics, consolidate, and compute scores.

    Returns None if no metrics found (caller decides error handling).
    """
    metrics_list = await MetricsService.get_latest_metrics_for_scoring(
        db, project_id, snapshot_type
    )
    if not metrics_list:
        return None

    latest_period_end = metrics_list[0].period_end
    same_period = [m for m in metrics_list if m.period_end == latest_period_end]
    metrics_db = _consolidate_metrics(same_period)
    metrics = MetricsCreate.from_db(metrics_db)

    score_service = ScoreComputationService(config)
    indicators, scores = score_service.compute(metrics, sev1_incident=metrics_db.sev1_incident)
    return ScoreResponse(indicators=indicators, scores=scores)


@router.post("/batch")
@limiter.limit("30/minute")
async def get_batch_scores(
    request: Request,
    body: BatchScoresRequest,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    cache: OptionalScoreCache,
) -> BatchScoresResponse:
    """Get scores for multiple projects in a single request.

    Uses Redis MGET for cached results, computes and caches misses.
    """
    project_ids = body.project_ids
    snapshot_type = body.snapshot_type
    results: dict[str, ScoreResponse] = {}
    errors: dict[str, str] = {}

    # Try cache first
    cached_map: dict[str, dict | None] = {}
    if cache:
        cached_map = await cache.mget(project_ids, snapshot_type.value)

    to_compute: list[str] = []
    for pid in project_ids:
        cached = cached_map.get(pid)
        if cached:
            results[pid] = ScoreResponse(**cached)
        else:
            to_compute.append(pid)

    # Compute misses
    for pid in to_compute:
        try:
            resp = await _compute_latest_scores(db, UUID(pid), snapshot_type, config)
            if resp is None:
                errors[pid] = "No metrics found"
                continue

            results[pid] = resp
            if cache:
                await cache.set(pid, resp.model_dump(), snapshot_type.value)
        except Exception as e:
            logger.warning("batch score computation failed for %s: %s", pid, e)
            errors[pid] = str(e)

    return BatchScoresResponse(scores=results, errors=errors)


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
