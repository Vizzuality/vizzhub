"""Metrics input endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.core.api.deps import (
    DBSession,
    OptionalScoreCache,
    ScoringConfigDep,
    get_project_or_404,
    limiter,
)
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission

MetricsEditor = Annotated[TokenData, Depends(require_permission(Action.SCORECARD_EDIT_METRICS))]
ScorecardViewer = Annotated[TokenData, Depends(require_permission(Action.SCORECARD_VIEW))]
from app.core.exceptions import MetricsNotFoundError
from app.modules.scorecard.models.indicators import IndicatorsCreate
from app.modules.scorecard.models.metrics import (
    Metrics,
    MetricsCreate,
    MetricsDB,
    MetricsWithScores,
    SnapshotType,
)
from app.modules.scorecard.models.scores import FinalScore
from app.modules.scorecard.services.metrics_service import MetricsService
from app.modules.scorecard.services.score_computation import ScoreComputationService

router = APIRouter()


def _build_metrics_with_scores(
    metrics_db: MetricsDB,
    metrics: MetricsCreate,
    indicators: IndicatorsCreate,
    scores: FinalScore,
) -> MetricsWithScores:
    """Build a MetricsWithScores response from DB record and computed values."""
    return MetricsWithScores(
        id=str(metrics_db.id),
        project_id=str(metrics_db.project_id),
        period_year=metrics_db.period_year,
        period_month=metrics_db.period_month,
        snapshot_type=metrics_db.snapshot_type,
        weights_applied=metrics_db.weights_applied,
        targets_applied=metrics_db.targets_applied,
        created_at=metrics_db.created_at,
        indicators=indicators.model_dump(),
        scores=scores.model_dump(),
        evm_data=metrics.evm_data,
        milestones=metrics.milestones,
        jira_defects=metrics.jira_defects,
        flow_metrics=metrics.flow_metrics,
        github_metrics=metrics.github_metrics,
        test_maturity=metrics.test_maturity,
        architecture=metrics.architecture,
        pm_satisfaction=metrics.pm_satisfaction,
        client_survey=metrics.client_survey,
        strategic_impact=metrics.strategic_impact,
        governance_exceptions=metrics.governance_exceptions,
        sev1_incident=metrics.sev1_incident,
    )


@router.get("/project/{project_id}")
@limiter.limit("100/minute")
async def list_project_metrics(
    request: Request,
    project_id: UUID,
    current_user: ScorecardViewer,
    db: DBSession,
    snapshot_type: SnapshotType = SnapshotType.CUMULATIVE,
) -> list[Metrics]:
    """List all metrics for a project. Requires authentication.

    Args:
        snapshot_type: Filter by snapshot type (default: cumulative)
    """
    await get_project_or_404(db, project_id)

    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .where(MetricsDB.snapshot_type == snapshot_type.value)
        .order_by(MetricsDB.period_end.desc())
    )
    metrics_list = result.scalars().all()
    return [Metrics.from_db(m) for m in metrics_list]


@router.post("/project/{project_id}", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_metrics(
    request: Request,
    project_id: UUID,
    metrics: MetricsCreate,
    current_user: MetricsEditor,
    db: DBSession,
    config: ScoringConfigDep,
    cache: OptionalScoreCache,
) -> Metrics:
    """Create or update metrics for a project. Uses upsert behavior.

    If metrics already exist for the same (project, period_year, period_month, snapshot_type),
    they will be updated with the new values.
    """
    project = await get_project_or_404(db, project_id)

    # For finished projects, only allow end-of-project metrics
    if project.status == "finished":
        metrics_dict = metrics.model_dump(exclude_unset=True)
        allowed_fields = {
            "period_start",
            "period_end",
            "period_year",
            "period_month",
            "snapshot_type",
            "strategic_impact",
            "client_survey",
            "sev1_incident",
        }
        provided_fields = set(metrics_dict.keys())
        disallowed = provided_fields - allowed_fields

        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project is finished. Only end-of-project metrics can be updated. Disallowed: {sorted(disallowed)}",
            )

    db_data = metrics.to_db_dict()

    db_metrics = await MetricsService.upsert_metrics(
        db,
        project_id,
        metrics.period_year,
        metrics.period_month,
        metrics.snapshot_type,
        config,
        db_data,
    )

    if cache:
        await cache.invalidate(str(project_id))

    return Metrics.from_db(db_metrics)


@router.get("/{metrics_id}")
@limiter.limit("100/minute")
async def get_metrics(
    request: Request, metrics_id: UUID, current_user: ScorecardViewer, db: DBSession
) -> Metrics:
    """Get specific metrics by ID. Requires authentication."""
    result = await db.execute(select(MetricsDB).where(MetricsDB.id == str(metrics_id)))
    metrics = result.scalar_one_or_none()
    if metrics is None:
        raise MetricsNotFoundError(str(metrics_id))
    return Metrics.from_db(metrics)


@router.delete("/{metrics_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_metrics(
    request: Request,
    metrics_id: UUID,
    current_user: MetricsEditor,
    db: DBSession,
    cache: OptionalScoreCache,
) -> None:
    """Delete metrics by ID."""
    result = await db.execute(select(MetricsDB).where(MetricsDB.id == str(metrics_id)))
    metrics = result.scalar_one_or_none()
    if metrics is None:
        raise MetricsNotFoundError(str(metrics_id))

    project_id = metrics.project_id
    await db.delete(metrics)

    if cache:
        await cache.invalidate(str(project_id))


@router.get("/project/{project_id}/history")
@limiter.limit("100/minute")
async def get_project_metrics_history(
    request: Request,
    project_id: UUID,
    current_user: ScorecardViewer,
    db: DBSession,
    config: ScoringConfigDep,
    snapshot_type: SnapshotType = SnapshotType.CUMULATIVE,
    limit: int = 12,
) -> list[MetricsWithScores]:
    """Get metrics history for a project with computed scores.

    Args:
        snapshot_type: Filter by snapshot type (default: cumulative)

    Returns metrics ordered by period (most recent first).
    """
    await get_project_or_404(db, project_id)

    history = await MetricsService.get_project_history(
        db, project_id, snapshot_type=snapshot_type, limit=limit
    )

    score_service = ScoreComputationService(config)
    responses = []
    for metrics_db in history:
        metrics = MetricsCreate.from_db(metrics_db)
        indicators, scores = score_service.compute(metrics, sev1_incident=metrics_db.sev1_incident)
        responses.append(_build_metrics_with_scores(metrics_db, metrics, indicators, scores))

    return responses


@router.get("/project/{project_id}/{year}/{month}")
@limiter.limit("100/minute")
async def get_metrics_by_period(
    request: Request,
    project_id: UUID,
    year: int,
    month: int,
    current_user: ScorecardViewer,
    db: DBSession,
    config: ScoringConfigDep,
    snapshot_type: SnapshotType = SnapshotType.CUMULATIVE,
) -> MetricsWithScores:
    """Get metrics for a specific period with computed scores.

    Args:
        snapshot_type: Filter by snapshot type (default: cumulative)
    """
    await get_project_or_404(db, project_id)

    metrics_db = await MetricsService.get_metrics(db, project_id, year, month, snapshot_type)
    if not metrics_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metrics of type '{snapshot_type.value}' not found for {year}-{month:02d}",
        )

    score_service = ScoreComputationService(config)
    metrics = MetricsCreate.from_db(metrics_db)
    indicators, scores = score_service.compute(metrics, sev1_incident=metrics_db.sev1_incident)

    return _build_metrics_with_scores(metrics_db, metrics, indicators, scores)
