"""Data collection endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.core.api.deps import (
    CurrentUser,
    DBSession,
    OptionalScoreCache,
    get_project_or_404,
    limiter,
)
from app.core.exceptions import ConfigurationError
from app.modules.scorecard.models.metrics import Metrics, MetricsDB, SnapshotType
from app.modules.scorecard.services.collectors.github import GitHubCollector
from app.modules.scorecard.services.collectors.jira import JiraCollector

router = APIRouter()


@router.post(
    "/project/{project_id}/jira",
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def collect_jira_metrics(
    request: Request,
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    cache: OptionalScoreCache,
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
        collected = await collector.collect(
            project.jira_project_key, end_date=project.end_date
        )
        raw_metrics = collected.model_dump()
    except ConfigurationError:
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

    # Get existing CUMULATIVE metrics to preserve manually-entered fields
    # (collectors always work with cumulative data - project start to current day)
    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .where(MetricsDB.snapshot_type == SnapshotType.CUMULATIVE.value)
        .order_by(MetricsDB.period_year.desc(), MetricsDB.period_month.desc())
        .limit(1)
    )
    existing_metrics = result.scalar_one_or_none()

    # Get preserved fields from existing metrics (manual + GitHub fields)
    preserved = (
        existing_metrics.get_preserved_fields(include_github=True)
        if existing_metrics
        else MetricsDB.get_default_preserved_fields(include_github=True)
    )

    # Build new metrics with Jira data + preserved fields
    # These collector endpoints create cumulative metrics (project start to current day)
    db_metrics = MetricsDB.from_collector_data(
        project_id=str(project_id),
        period_start=period_start,
        period_end=period_end,
        snapshot_type=SnapshotType.CUMULATIVE,
        jira_data=raw_metrics,
        preserved=preserved,
    )

    db.add(db_metrics)
    await db.flush()
    await db.refresh(db_metrics)

    if cache:
        await cache.invalidate(str(project_id))

    return Metrics.from_db(db_metrics)


@router.post(
    "/project/{project_id}/github",
    status_code=status.HTTP_200_OK,
)
@limiter.limit("10/minute")
async def collect_github_metrics(
    request: Request,
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    cache: OptionalScoreCache,
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

    collector = GitHubCollector(db=db)
    try:
        collected = await collector.collect(project.github_repo)
        raw_metrics = collected.model_dump()
    except ConfigurationError:
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

    # Get the most recent CUMULATIVE metrics record for this project
    # (collectors always work with cumulative data - project start to current day)
    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .where(MetricsDB.snapshot_type == SnapshotType.CUMULATIVE.value)
        .order_by(MetricsDB.period_year.desc(), MetricsDB.period_month.desc())
        .limit(1)
    )
    existing_metrics = result.scalar_one_or_none()

    if existing_metrics:
        # Update existing record with GitHub data
        existing_metrics.prs_without_review = raw_metrics.get("prs_without_review", 0)
        existing_metrics.total_merged_prs = raw_metrics.get("total_merged_prs", 0)
        existing_metrics.high_severity_vulns = raw_metrics.get("high_severity_vulns", 0)
        existing_metrics.high_severity_vulns_total = raw_metrics.get(
            "high_severity_vulns_total", 0
        )
        existing_metrics.pr_size_median = raw_metrics.get("pr_size_median")
        existing_metrics.review_turnaround_hours = raw_metrics.get(
            "review_turnaround_hours"
        )
        existing_metrics.deployment_frequency = raw_metrics.get("deployment_frequency")
        existing_metrics.release_count_90d = raw_metrics.get("release_count_90d", 0)
        existing_metrics.change_failure_rate = raw_metrics.get("change_failure_rate")
        existing_metrics.total_releases = raw_metrics.get("total_releases", 0)
        existing_metrics.failed_releases = raw_metrics.get("failed_releases", 0)

        await db.flush()
        await db.refresh(existing_metrics)

        if cache:
            await cache.invalidate(str(project_id))

        return Metrics.from_db(existing_metrics)
    else:
        # Create new record with only GitHub data
        # These collector endpoints create cumulative metrics (project start to current day)
        now = datetime.now(timezone.utc)
        period_start = project.start_date or now.date()
        period_end = now.date()

        db_metrics = MetricsDB.from_collector_data(
            project_id=str(project_id),
            period_start=period_start,
            period_end=period_end,
            snapshot_type=SnapshotType.CUMULATIVE,
            github_data=raw_metrics,
        )
        db.add(db_metrics)
        await db.flush()
        await db.refresh(db_metrics)

        if cache:
            await cache.invalidate(str(project_id))

        return Metrics.from_db(db_metrics)
