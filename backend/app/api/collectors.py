"""Data collection endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, get_project_or_404, limiter
from app.core.exceptions import ConfigurationError
from app.models.metrics import Metrics, MetricsDB
from app.services.collectors.github import GitHubCollector
from app.services.collectors.jira import JiraCollector

router = APIRouter()


@router.post(
    "/project/{project_id}/jira",
    response_model=Metrics,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def collect_jira_metrics(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> Metrics:
    """
    Collect metrics from Jira for a project and save to database.

    Requires authentication.

    Args:
        project_id: UUID of the project
        current_user: Authenticated user
        db: Database session

    Returns:
        Created metrics object

    Raises:
        ProjectNotFoundError: If project doesn't exist
        HTTPException: If project has no Jira key or collection fails
    """
    # Get project
    project = await get_project_or_404(db, project_id)

    # Block collection for finished projects
    if project.status == "finished":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot collect metrics for finished projects. Reopen the project first.",
        )

    # Check if project has Jira key
    if not project.jira_project_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project does not have a Jira project key configured",
        )

    # Collect metrics from Jira
    collector = JiraCollector(db=db)
    try:
        raw_metrics = await collector.collect(
            project.jira_project_key, end_date=project.end_date
        )
    except ConfigurationError:
        await collector.close()
        raise
    except ValueError as e:
        # Invalid project key format
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid project key format",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to collect metrics",
        ) from e
    finally:
        await collector.close()

    # Create metrics object
    now = datetime.now(timezone.utc)
    period_start = project.start_date or now.date()
    period_end = now.date()

    # Map raw metrics to database structure
    jira_defects = {
        "bugs_total": raw_metrics.get("bugs_total", 0),
        "tasks_completed": raw_metrics.get("tasks_completed", 0),
        "escaped_defects": raw_metrics.get("escaped_defects", 0),
        "mttr_hours": raw_metrics.get("mttr_hours"),
        "incidents_count": raw_metrics.get("incidents_count", 0),
        "post_contract_tasks": raw_metrics.get("post_contract_tasks"),
    }

    flow_metrics = {
        "lead_time_days": raw_metrics.get("lead_time_days"),
        "lead_time_sample_size": raw_metrics.get("lead_time_sample_size", 0),
        "commitment_reliability": raw_metrics.get("commitment_reliability"),
        "committed_issues": raw_metrics.get("committed_issues", 0),
        "single_sprint_issues": raw_metrics.get("single_sprint_issues", 0),
        "multi_sprint_issues": raw_metrics.get("multi_sprint_issues", 0),
        "total_stories": raw_metrics.get("total_stories", 0),
        "stories_with_reviewer": raw_metrics.get("stories_with_reviewer", 0),
    }

    # Get existing metrics to preserve manually-entered fields
    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.created_at.desc())
        .limit(1)
    )
    existing_metrics = result.scalar_one_or_none()

    # Preserve manually-entered fields from existing metrics
    preserved_fields = {}
    if existing_metrics:
        preserved_fields = {
            "evm_data": existing_metrics.evm_data,
            "milestones": existing_metrics.milestones,
            "governance_exceptions": existing_metrics.governance_exceptions,
            "pm_satisfaction": existing_metrics.pm_satisfaction,
            "test_maturity": existing_metrics.test_maturity,
            "architecture_checklist": existing_metrics.architecture_checklist,
            "strategic_impact": existing_metrics.strategic_impact,
            "client_survey": existing_metrics.client_survey,
            "sev1_incident": existing_metrics.sev1_incident,
            "github_metrics": existing_metrics.github_metrics,
        }

    db_metrics = MetricsDB(
        project_id=str(project_id),
        period_start=period_start,
        period_end=period_end,
        jira_defects=jira_defects,
        flow_metrics=flow_metrics,
        sev1_incident=preserved_fields.get("sev1_incident", False),
        evm_data=preserved_fields.get("evm_data"),
        milestones=preserved_fields.get("milestones"),
        governance_exceptions=preserved_fields.get("governance_exceptions"),
        pm_satisfaction=preserved_fields.get("pm_satisfaction"),
        test_maturity=preserved_fields.get("test_maturity"),
        architecture_checklist=preserved_fields.get("architecture_checklist"),
        strategic_impact=preserved_fields.get("strategic_impact"),
        client_survey=preserved_fields.get("client_survey"),
        github_metrics=preserved_fields.get("github_metrics"),
    )

    db.add(db_metrics)
    await db.flush()
    await db.refresh(db_metrics)
    return Metrics.model_validate(db_metrics)


@router.post(
    "/project/{project_id}/github",
    response_model=Metrics,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/minute")
async def collect_github_metrics(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> Metrics:
    """
    Collect metrics from GitHub for a project and update latest metrics record.

    Requires authentication.

    Args:
        project_id: UUID of the project
        current_user: Authenticated user
        db: Database session

    Returns:
        Updated metrics object

    Raises:
        ProjectNotFoundError: If project doesn't exist
        HTTPException: If project has no GitHub repo or collection fails
    """
    project = await get_project_or_404(db, project_id)

    # Block collection for finished projects
    if project.status == "finished":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot collect metrics for finished projects. Reopen the project first.",
        )

    if not project.github_repo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project does not have a GitHub repository configured",
        )

    collector = GitHubCollector()
    try:
        raw_metrics = await collector.collect(project.github_repo)
    except ConfigurationError:
        await collector.close()
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository format",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to collect metrics from GitHub",
        ) from e
    finally:
        await collector.close()

    github_metrics = {
        "prs_without_review": raw_metrics.get("prs_without_review", 0),
        "total_merged_prs": raw_metrics.get("total_merged_prs", 0),
        "pr_review_ratio": raw_metrics.get("pr_review_ratio"),
        "high_severity_vulns": raw_metrics.get("high_severity_vulns", 0),
        "high_severity_vulns_total": raw_metrics.get("high_severity_vulns_total", 0),
        "pr_size_median": raw_metrics.get("pr_size_median"),
        "review_turnaround_hours": raw_metrics.get("review_turnaround_hours"),
        "deployment_frequency": raw_metrics.get("deployment_frequency"),
        "release_count_90d": raw_metrics.get("release_count_90d", 0),
        "change_failure_rate": raw_metrics.get("change_failure_rate"),
        "total_releases": raw_metrics.get("total_releases", 0),
        "failed_releases": raw_metrics.get("failed_releases", 0),
    }

    # Get the most recent metrics record for this project
    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.created_at.desc())
        .limit(1)
    )
    existing_metrics = result.scalar_one_or_none()

    if existing_metrics:
        existing_metrics.github_metrics = github_metrics
        await db.flush()
        await db.refresh(existing_metrics)
        return Metrics.model_validate(existing_metrics)
    else:
        now = datetime.now(timezone.utc)
        period_start = project.start_date or now.date()
        period_end = now.date()

        db_metrics = MetricsDB(
            project_id=str(project_id),
            period_start=period_start,
            period_end=period_end,
            github_metrics=github_metrics,
        )
        db.add(db_metrics)
        await db.flush()
        await db.refresh(db_metrics)
        return Metrics.model_validate(db_metrics)
