"""Data collection endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import ProjectNotFoundError
from app.models.metrics import Metrics, MetricsDB
from app.models.project import ProjectDB
from app.services.collectors.jira import JiraCollector

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


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
    result = await db.execute(select(ProjectDB).where(ProjectDB.id == str(project_id)))
    project = result.scalar_one_or_none()
    if project is None:
        raise ProjectNotFoundError(str(project_id))

    # Check if project has Jira key
    if not project.jira_project_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project does not have a Jira project key configured",
        )

    # Collect metrics from Jira
    collector = JiraCollector(db=db)
    try:
        raw_metrics = await collector.collect(project.jira_project_key)
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
        "bugs_closed": raw_metrics.get("bugs_closed", 0),
        "tasks_completed": raw_metrics.get("tasks_completed", 0),
        "escaped_defects": raw_metrics.get("escaped_defects", 0),
        "mttr_hours": raw_metrics.get("mttr_hours"),
        "incidents_count": raw_metrics.get("incidents_count", 0),
    }

    flow_metrics = {
        "lead_time_days": raw_metrics.get("lead_time_days"),
        "flow_efficiency": raw_metrics.get("flow_efficiency"),
        "commitment_reliability": raw_metrics.get("commitment_reliability"),
        "total_stories": raw_metrics.get("total_stories", 0),
        "stories_with_reviewer": raw_metrics.get("stories_with_reviewer", 0),
    }

    db_metrics = MetricsDB(
        project_id=str(project_id),
        period_start=period_start,
        period_end=period_end,
        jira_defects=jira_defects,
        flow_metrics=flow_metrics,
        sev1_incident=False,  # Default to False, can be updated later
    )

    db.add(db_metrics)
    await db.flush()
    await db.refresh(db_metrics)
    return Metrics.model_validate(db_metrics)
