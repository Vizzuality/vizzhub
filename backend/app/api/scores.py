"""Score computation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, get_project_or_404, limiter
from app.core.exceptions import MetricsNotFoundError
from app.models.indicators import IndicatorsCreate
from app.models.metrics import MetricsCreate, MetricsDB
from app.models.scores import FinalScore
from app.services.calculators.final_score import FinalScoreCalculator
from app.services.normalizers.indicators import IndicatorNormalizer

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
    normalizer = IndicatorNormalizer(config)
    calculator = FinalScoreCalculator(config)

    indicators = normalizer.normalize_all(score_request.metrics)

    total_prs = None
    if score_request.metrics.github_metrics:
        total_prs = score_request.metrics.github_metrics.total_merged_prs

    scores = calculator.calculate_all(
        indicators,
        sev1_incident=score_request.sev1_incident,
        total_prs=total_prs,
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
) -> ScoreResponse:
    """Calculate scores from a project's latest metrics.

    Since collectors create separate records, this endpoint consolidates
    metrics from the same period_end date, taking the most recent non-null
    value for each field.
    """
    await get_project_or_404(db, project_id)

    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.period_end.desc(), MetricsDB.created_at.desc())
        .limit(20)
    )
    metrics_list = list(result.scalars().all())
    if not metrics_list:
        raise MetricsNotFoundError(str(project_id))

    latest_period_end = metrics_list[0].period_end
    same_period = [m for m in metrics_list if m.period_end == latest_period_end]

    metrics_db = _consolidate_metrics(same_period)
    metrics = MetricsCreate.from_db(metrics_db)

    normalizer = IndicatorNormalizer(config)
    calculator = FinalScoreCalculator(config)

    indicators = normalizer.normalize_all(metrics)

    total_prs = None
    if metrics.github_metrics:
        total_prs = metrics.github_metrics.total_merged_prs

    scores = calculator.calculate_all(
        indicators,
        sev1_incident=metrics_db.sev1_incident,
        total_prs=total_prs,
    )

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
    limit: int = 10,
) -> list[ScoreResponse]:
    """Get score history for a project."""
    await get_project_or_404(db, project_id)

    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.period_end.desc(), MetricsDB.created_at.desc())
        .limit(limit)
    )
    metrics_list = result.scalars().all()

    normalizer = IndicatorNormalizer(config)
    calculator = FinalScoreCalculator(config)

    responses = []
    for metrics_db in metrics_list:
        metrics = MetricsCreate.from_db(metrics_db)
        indicators = normalizer.normalize_all(metrics)

        total_prs = None
        if metrics.github_metrics:
            total_prs = metrics.github_metrics.total_merged_prs

        scores = calculator.calculate_all(
            indicators,
            sev1_incident=metrics_db.sev1_incident,
            total_prs=total_prs,
        )
        responses.append(ScoreResponse(indicators=indicators, scores=scores))

    return responses
