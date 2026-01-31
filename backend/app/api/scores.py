"""Score computation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, get_project_or_404, limiter
from app.core.exceptions import MetricsNotFoundError
from app.models.indicators import IndicatorsCreate
from app.models.metrics import MetricsCreate, MetricsDB, SnapshotType
from app.models.scores import FinalScore
from app.services.metrics_service import MetricsService
from app.services.score_computation import ScoreComputationService

router = APIRouter()


class ScoreRequest(BaseModel):
    """Request body for ad-hoc score calculation."""

    metrics: MetricsCreate
    sev1_incident: bool = False


class ScoreResponse(BaseModel):
    """Response with calculated scores."""

    indicators: IndicatorsCreate
    scores: FinalScore


@router.post("/calculate", response_model=ScoreResponse)
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


@router.get("/project/{project_id}", response_model=ScoreResponse)
@limiter.limit("100/minute")
async def get_project_scores(
    request: Request,
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    snapshot_type: SnapshotType = SnapshotType.CUMULATIVE,
) -> ScoreResponse:
    """Calculate scores from a project's latest metrics.

    Args:
        snapshot_type: Filter by snapshot type (default: cumulative)

    Since collectors create separate records, this endpoint consolidates
    metrics from the same period_end date, taking the most recent non-null
    value for each field.
    """
    await get_project_or_404(db, project_id)

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
    """Consolidate multiple metrics records, taking first non-null value for each field."""
    if len(metrics_list) == 1:
        return metrics_list[0]

    base = metrics_list[0]

    # Normalized columns to consolidate
    normalized_fields = [
        # EVM
        "budget_total", "cost_to_date", "percent_completed", "percent_planned",
        # Defects
        "bugs_total", "tasks_completed", "escaped_defects", "mttr_hours",
        "incidents_count", "post_contract_tasks",
        # Flow
        "lead_time_days", "lead_time_sample_size", "commitment_reliability",
        "committed_issues", "single_sprint_issues", "multi_sprint_issues",
        "total_stories", "stories_with_reviewer",
        # GitHub
        "prs_without_review", "total_merged_prs", "high_severity_vulns",
        "high_severity_vulns_total", "pr_size_median", "review_turnaround_hours",
        "deployment_frequency", "release_count_90d", "change_failure_rate",
        "total_releases", "failed_releases",
        # Manual
        "governance_exceptions", "strategic_impact",
    ]

    # JSON fields to consolidate
    json_fields = [
        "milestones", "test_maturity", "architecture",
        "pm_satisfaction", "client_survey",
    ]

    for field in normalized_fields + json_fields:
        if getattr(base, field) is None:
            for m in metrics_list[1:]:
                value = getattr(m, field)
                if value is not None:
                    setattr(base, field, value)
                    break

    if not base.sev1_incident:
        for m in metrics_list[1:]:
            if m.sev1_incident:
                base.sev1_incident = True
                break

    return base


@router.get("/project/{project_id}/history", response_model=list[ScoreResponse])
async def get_project_score_history(
    project_id: UUID,
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
