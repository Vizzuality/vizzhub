"""Score computation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, get_project_or_404, limiter
from app.core.exceptions import MetricsNotFoundError
from app.models.indicators import IndicatorsCreate
from app.models.metrics import (
    ArchitectureChecklist,
    ClientSurvey,
    EVMData,
    FlowMetrics,
    GitHubMetrics,
    JiraDefectMetrics,
    MetricsCreate,
    MetricsDB,
    Milestone,
    PMSatisfaction,
    StrategicImpact,
    TestMaturity,
)
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

    # Get all metrics for latest period_end to consolidate
    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.period_end.desc(), MetricsDB.created_at.desc())
        .limit(20)  # Get enough records to consolidate
    )
    metrics_list = result.scalars().all()
    if not metrics_list:
        raise MetricsNotFoundError(str(project_id))

    # Filter to same period_end as latest
    latest_period_end = metrics_list[0].period_end
    same_period = [m for m in metrics_list if m.period_end == latest_period_end]

    # Consolidate metrics from same period
    metrics_db = _consolidate_metrics(same_period)
    metrics = _db_to_metrics_create(metrics_db)

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

    # Start with the most recent record
    base = metrics_list[0]

    # Fields to consolidate (take first non-null)
    fields = [
        "evm_data", "milestones", "jira_defects", "flow_metrics",
        "github_metrics", "test_maturity", "architecture",
        "pm_satisfaction", "client_survey", "strategic_impact",
        "governance_exceptions",
    ]

    for field in fields:
        if getattr(base, field) is None:
            for m in metrics_list[1:]:
                value = getattr(m, field)
                if value is not None:
                    setattr(base, field, value)
                    break

    # Special handling for sev1_incident (True if any record has it)
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
        metrics = _db_to_metrics_create(metrics_db)
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


def _db_to_metrics_create(db: MetricsDB) -> MetricsCreate:
    """Convert DB model to MetricsCreate for calculation."""
    return MetricsCreate(
        period_start=db.period_start,
        period_end=db.period_end,
        evm_data=EVMData(**db.evm_data) if db.evm_data else None,
        milestones=[Milestone(**m) for m in db.milestones] if db.milestones else None,
        jira_defects=JiraDefectMetrics(**db.jira_defects) if db.jira_defects else None,
        flow_metrics=FlowMetrics(**db.flow_metrics) if db.flow_metrics else None,
        github_metrics=GitHubMetrics(**db.github_metrics) if db.github_metrics else None,
        test_maturity=TestMaturity(**db.test_maturity) if db.test_maturity else None,
        architecture=ArchitectureChecklist(**db.architecture) if db.architecture else None,
        pm_satisfaction=PMSatisfaction(**db.pm_satisfaction) if db.pm_satisfaction else None,
        client_survey=ClientSurvey(**db.client_survey) if db.client_survey else None,
        strategic_impact=StrategicImpact(db.strategic_impact) if db.strategic_impact else None,
        governance_exceptions=db.governance_exceptions,
        sev1_incident=db.sev1_incident,
    )
