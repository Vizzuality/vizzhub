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
    """
    project = await get_project_or_404(db, project_id)

    if project.status == "finished":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot collect metrics for finished projects. Reopen the project first.",
        )

    if not project.jira_project_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project does not have a Jira project key configured",
        )

    collector = JiraCollector(db=db)
    try:
        raw_metrics = await collector.collect(
            project.jira_project_key, end_date=project.end_date
        )
    except ConfigurationError:
        await collector.close()
        raise
    except ValueError as e:
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

    now = datetime.now(timezone.utc)
    period_start = project.start_date or now.date()
    period_end = now.date()

    # Get existing metrics to preserve manually-entered fields
    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.created_at.desc())
        .limit(1)
    )
    existing_metrics = result.scalar_one_or_none()

    # Build new metrics with Jira data + preserved manual fields
    db_metrics = MetricsDB(
        project_id=str(project_id),
        period_start=period_start,
        period_end=period_end,
        # Jira defect metrics (normalized columns)
        bugs_total=raw_metrics.get("bugs_total", 0),
        tasks_completed=raw_metrics.get("tasks_completed", 0),
        escaped_defects=raw_metrics.get("escaped_defects", 0),
        mttr_hours=raw_metrics.get("mttr_hours"),
        incidents_count=raw_metrics.get("incidents_count", 0),
        post_contract_tasks=raw_metrics.get("post_contract_tasks"),
        # Jira flow metrics (normalized columns)
        lead_time_days=raw_metrics.get("lead_time_days"),
        lead_time_sample_size=raw_metrics.get("lead_time_sample_size", 0),
        commitment_reliability=raw_metrics.get("commitment_reliability"),
        committed_issues=raw_metrics.get("committed_issues", 0),
        single_sprint_issues=raw_metrics.get("single_sprint_issues", 0),
        multi_sprint_issues=raw_metrics.get("multi_sprint_issues", 0),
        total_stories=raw_metrics.get("total_stories", 0),
        stories_with_reviewer=raw_metrics.get("stories_with_reviewer", 0),
        # Preserved fields from existing metrics
        sev1_incident=existing_metrics.sev1_incident if existing_metrics else False,
        budget_total=existing_metrics.budget_total if existing_metrics else None,
        cost_to_date=existing_metrics.cost_to_date if existing_metrics else None,
        percent_completed=existing_metrics.percent_completed if existing_metrics else None,
        percent_planned=existing_metrics.percent_planned if existing_metrics else None,
        governance_exceptions=existing_metrics.governance_exceptions if existing_metrics else None,
        strategic_impact=existing_metrics.strategic_impact if existing_metrics else None,
        # GitHub metrics (preserved)
        prs_without_review=existing_metrics.prs_without_review if existing_metrics else None,
        total_merged_prs=existing_metrics.total_merged_prs if existing_metrics else None,
        high_severity_vulns=existing_metrics.high_severity_vulns if existing_metrics else None,
        high_severity_vulns_total=existing_metrics.high_severity_vulns_total if existing_metrics else None,
        pr_size_median=existing_metrics.pr_size_median if existing_metrics else None,
        review_turnaround_hours=existing_metrics.review_turnaround_hours if existing_metrics else None,
        deployment_frequency=existing_metrics.deployment_frequency if existing_metrics else None,
        release_count_90d=existing_metrics.release_count_90d if existing_metrics else None,
        change_failure_rate=existing_metrics.change_failure_rate if existing_metrics else None,
        total_releases=existing_metrics.total_releases if existing_metrics else None,
        failed_releases=existing_metrics.failed_releases if existing_metrics else None,
        # JSON fields (preserved)
        milestones=existing_metrics.milestones if existing_metrics else None,
        pm_satisfaction=existing_metrics.pm_satisfaction if existing_metrics else None,
        test_maturity=existing_metrics.test_maturity if existing_metrics else None,
        architecture=existing_metrics.architecture if existing_metrics else None,
        client_survey=existing_metrics.client_survey if existing_metrics else None,
    )

    db.add(db_metrics)
    await db.flush()
    await db.refresh(db_metrics)
    return Metrics.from_db(db_metrics)


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
    """
    project = await get_project_or_404(db, project_id)

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

    # Get the most recent metrics record for this project
    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.created_at.desc())
        .limit(1)
    )
    existing_metrics = result.scalar_one_or_none()

    if existing_metrics:
        # Update existing record with GitHub data
        existing_metrics.prs_without_review = raw_metrics.get("prs_without_review", 0)
        existing_metrics.total_merged_prs = raw_metrics.get("total_merged_prs", 0)
        existing_metrics.high_severity_vulns = raw_metrics.get("high_severity_vulns", 0)
        existing_metrics.high_severity_vulns_total = raw_metrics.get("high_severity_vulns_total", 0)
        existing_metrics.pr_size_median = raw_metrics.get("pr_size_median")
        existing_metrics.review_turnaround_hours = raw_metrics.get("review_turnaround_hours")
        existing_metrics.deployment_frequency = raw_metrics.get("deployment_frequency")
        existing_metrics.release_count_90d = raw_metrics.get("release_count_90d", 0)
        existing_metrics.change_failure_rate = raw_metrics.get("change_failure_rate")
        existing_metrics.total_releases = raw_metrics.get("total_releases", 0)
        existing_metrics.failed_releases = raw_metrics.get("failed_releases", 0)

        await db.flush()
        await db.refresh(existing_metrics)
        return Metrics.from_db(existing_metrics)
    else:
        # Create new record with only GitHub data
        now = datetime.now(timezone.utc)
        period_start = project.start_date or now.date()
        period_end = now.date()

        db_metrics = MetricsDB(
            project_id=str(project_id),
            period_start=period_start,
            period_end=period_end,
            prs_without_review=raw_metrics.get("prs_without_review", 0),
            total_merged_prs=raw_metrics.get("total_merged_prs", 0),
            high_severity_vulns=raw_metrics.get("high_severity_vulns", 0),
            high_severity_vulns_total=raw_metrics.get("high_severity_vulns_total", 0),
            pr_size_median=raw_metrics.get("pr_size_median"),
            review_turnaround_hours=raw_metrics.get("review_turnaround_hours"),
            deployment_frequency=raw_metrics.get("deployment_frequency"),
            release_count_90d=raw_metrics.get("release_count_90d", 0),
            change_failure_rate=raw_metrics.get("change_failure_rate"),
            total_releases=raw_metrics.get("total_releases", 0),
            failed_releases=raw_metrics.get("failed_releases", 0),
        )
        db.add(db_metrics)
        await db.flush()
        await db.refresh(db_metrics)
        return Metrics.from_db(db_metrics)
