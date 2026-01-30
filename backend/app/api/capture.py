"""Period capture endpoint - orchestrates Jira/GitHub collection and metrics upsert."""

import calendar
from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, get_project_or_404, limiter
from app.core.exceptions import ConfigurationError
from app.models.metrics import MetricsCreate, MetricsDB, MetricsWithScores, SnapshotType
from app.models.project import ProjectDB
from app.services.collectors.github import GitHubCollector
from app.services.collectors.jira import JiraCollector
from app.services.metrics_service import MetricsService
from app.services.score_computation import ScoreComputationService

router = APIRouter()


class CapturePeriodRequest(BaseModel):
    """Request body for capturing a period.

    If year/month are not provided, defaults to current month with:
    - Cumulative: project start → today
    - Punctual: 1st of current month → today
    """

    year: int | None = Field(default=None, ge=2020, le=2100)
    month: int | None = Field(default=None, ge=1, le=12)
    force: bool = Field(default=False, description="Overwrite existing periods if they exist")


class CapturePeriodResponse(BaseModel):
    """Response containing both punctual and cumulative metrics."""

    punctual: MetricsWithScores
    cumulative: MetricsWithScores


def _last_day_of_month(year: int, month: int) -> date:
    """Get the last day of a month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def _first_day_of_month(year: int, month: int) -> date:
    """Get the first day of a month."""
    return date(year, month, 1)


async def _collect_from_jira(
    db: DBSession,
    project: ProjectDB,
    period_start: date,
    period_end: date,
) -> dict:
    """Collect metrics from Jira for a date range."""
    if not project.jira_project_key:
        return {}

    collector = JiraCollector(db=db)
    try:
        return await collector.collect(
            project.jira_project_key,
            end_date=project.end_date,
            period_start=period_start,
            period_end=period_end,
        )
    except ConfigurationError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect Jira metrics: {type(e).__name__}",
        ) from e
    finally:
        await collector.close()


async def _collect_from_github(
    project: ProjectDB,
    period_start: date,
    period_end: date,
) -> dict:
    """Collect metrics from GitHub for a date range."""
    if not project.github_repo:
        return {}

    collector = GitHubCollector()
    try:
        return await collector.collect(
            project.github_repo,
            period_start=period_start,
            period_end=period_end,
        )
    except ConfigurationError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect GitHub metrics: {type(e).__name__}",
        ) from e
    finally:
        await collector.close()


def _build_metrics_data(
    period_start: date,
    period_end: date,
    jira_data: dict,
    github_data: dict,
    preserved: dict,
) -> dict:
    """Build metrics data dict from collected data."""
    return {
        "period_start": period_start,
        "period_end": period_end,
        # Jira defect metrics
        "bugs_total": jira_data.get("bugs_total", 0) if jira_data else None,
        "tasks_completed": jira_data.get("tasks_completed", 0) if jira_data else None,
        "escaped_defects": jira_data.get("escaped_defects", 0) if jira_data else None,
        "mttr_hours": jira_data.get("mttr_hours") if jira_data else None,
        "incidents_count": jira_data.get("incidents_count", 0) if jira_data else None,
        "post_contract_tasks": jira_data.get("post_contract_tasks") if jira_data else None,
        # Jira flow metrics
        "lead_time_days": jira_data.get("lead_time_days") if jira_data else None,
        "lead_time_sample_size": jira_data.get("lead_time_sample_size", 0) if jira_data else None,
        "commitment_reliability": jira_data.get("commitment_reliability") if jira_data else None,
        "committed_issues": jira_data.get("committed_issues", 0) if jira_data else None,
        "single_sprint_issues": jira_data.get("single_sprint_issues", 0) if jira_data else None,
        "multi_sprint_issues": jira_data.get("multi_sprint_issues", 0) if jira_data else None,
        "total_stories": jira_data.get("total_stories", 0) if jira_data else None,
        "stories_with_reviewer": jira_data.get("stories_with_reviewer", 0) if jira_data else None,
        # GitHub metrics
        "prs_without_review": github_data.get("prs_without_review", 0) if github_data else None,
        "total_merged_prs": github_data.get("total_merged_prs", 0) if github_data else None,
        "high_severity_vulns": github_data.get("high_severity_vulns", 0) if github_data else None,
        "high_severity_vulns_total": github_data.get("high_severity_vulns_total", 0) if github_data else None,
        "pr_size_median": github_data.get("pr_size_median") if github_data else None,
        "review_turnaround_hours": github_data.get("review_turnaround_hours") if github_data else None,
        "deployment_frequency": github_data.get("deployment_frequency") if github_data else None,
        "release_count_90d": github_data.get("release_count_90d", 0) if github_data else None,
        "change_failure_rate": github_data.get("change_failure_rate") if github_data else None,
        "total_releases": github_data.get("total_releases", 0) if github_data else None,
        "failed_releases": github_data.get("failed_releases", 0) if github_data else None,
        # Preserved manual fields
        **preserved,
    }


def _build_response(
    db_metrics: MetricsDB,
    config: ScoringConfigDep,
) -> MetricsWithScores:
    """Build MetricsWithScores response from DB metrics."""
    score_service = ScoreComputationService(config)
    metrics = MetricsCreate.from_db(db_metrics)
    indicators, scores = score_service.compute(metrics, sev1_incident=db_metrics.sev1_incident)

    return MetricsWithScores(
        id=str(db_metrics.id),
        project_id=str(db_metrics.project_id),
        period_year=db_metrics.period_year,
        period_month=db_metrics.period_month,
        snapshot_type=db_metrics.snapshot_type,
        weights_applied=db_metrics.weights_applied,
        targets_applied=db_metrics.targets_applied,
        created_at=db_metrics.created_at,
        indicators=indicators.model_dump(),
        scores=scores.model_dump(),
    )


@router.post(
    "/{project_id}/capture-period",
    response_model=CapturePeriodResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
async def capture_period(
    request: Request,
    project_id: UUID,
    data: CapturePeriodRequest,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
) -> CapturePeriodResponse:
    """Capture metrics for a specific period from Jira and GitHub.

    This endpoint creates BOTH punctual and cumulative snapshots:
    - Punctual: metrics for the specified month only
    - Cumulative: metrics from project start through the specified month

    If year/month are not provided, defaults to current month:
    - Punctual: 1st of current month → today
    - Cumulative: project start → today

    Args:
        project_id: Project UUID
        data: Period specification (year, month, force) - year/month optional

    Returns:
        CapturePeriodResponse with both punctual and cumulative metrics

    Raises:
        400: Project missing Jira/GitHub configuration
        409: Period already captured (unless force=true)
    """
    project = await get_project_or_404(db, project_id)

    if not project.jira_project_key and not project.github_repo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project must have Jira or GitHub configured to capture periods",
        )

    # Default to current month if not provided
    today = date.today()
    year = data.year if data.year is not None else today.year
    month = data.month if data.month is not None else today.month
    use_today_as_end = data.year is None and data.month is None

    # Check if either snapshot type already exists
    existing_punctual = await MetricsService.get_metrics(
        db, project_id, year, month, SnapshotType.PUNCTUAL
    )
    existing_cumulative = await MetricsService.get_metrics(
        db, project_id, year, month, SnapshotType.CUMULATIVE
    )

    if (existing_punctual or existing_cumulative) and not data.force:
        existing_types = []
        if existing_punctual:
            existing_types.append("punctual")
        if existing_cumulative:
            existing_types.append("cumulative")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Metrics for {year}-{month:02d} already captured "
                f"({', '.join(existing_types)}). Use force=true to overwrite."
            ),
        )

    # Get preserved manual fields from existing metrics
    history = await MetricsService.get_project_history(db, project_id, limit=1)
    existing_metrics = history[0] if history else None
    preserved = (
        existing_metrics.get_preserved_fields(include_github=False)
        if existing_metrics
        else MetricsDB.get_default_preserved_fields(include_github=False)
    )

    # Define date ranges
    # When called without year/month (e.g., from "Collect Metrics" button), use today as end date
    # When called with specific year/month (e.g., historical capture), use last day of that month
    month_start = _first_day_of_month(year, month)
    month_end = today if use_today_as_end else _last_day_of_month(year, month)
    project_start = project.start_date

    # === PUNCTUAL: Collect and store for just this month ===
    punctual_jira = await _collect_from_jira(db, project, month_start, month_end)
    punctual_github = await _collect_from_github(project, month_start, month_end)
    punctual_data = _build_metrics_data(month_start, month_end, punctual_jira, punctual_github, preserved)

    punctual_db = await MetricsService.upsert_metrics(
        db, project_id, year, month, SnapshotType.PUNCTUAL, config, punctual_data
    )

    # === CUMULATIVE: Collect and store from project start to month end ===
    cumulative_jira = await _collect_from_jira(db, project, project_start, month_end)
    cumulative_github = await _collect_from_github(project, project_start, month_end)
    cumulative_data = _build_metrics_data(project_start, month_end, cumulative_jira, cumulative_github, preserved)

    cumulative_db = await MetricsService.upsert_metrics(
        db, project_id, year, month, SnapshotType.CUMULATIVE, config, cumulative_data
    )

    return CapturePeriodResponse(
        punctual=_build_response(punctual_db, config),
        cumulative=_build_response(cumulative_db, config),
    )
