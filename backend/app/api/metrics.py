"""Metrics input endpoints."""

from uuid import UUID

from fastapi import APIRouter, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import MetricsNotFoundError, ProjectNotFoundError
from app.models.metrics import Metrics, MetricsCreate, MetricsDB
from app.models.project import ProjectDB

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/project/{project_id}", response_model=list[Metrics])
@limiter.limit("100/minute")
async def list_project_metrics(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[Metrics]:
    """List all metrics for a project. Requires authentication."""
    result = await db.execute(
        select(ProjectDB).where(ProjectDB.id == str(project_id))
    )
    if result.scalar_one_or_none() is None:
        raise ProjectNotFoundError(str(project_id))

    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.period_end.desc())
    )
    metrics_list = result.scalars().all()
    return [Metrics.model_validate(m) for m in metrics_list]


@router.post("/project/{project_id}", response_model=Metrics, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def create_metrics(
    request: Request,
    project_id: UUID,
    metrics: MetricsCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> Metrics:
    """Create new metrics for a project. Requires authentication."""
    result = await db.execute(
        select(ProjectDB).where(ProjectDB.id == str(project_id))
    )
    if result.scalar_one_or_none() is None:
        raise ProjectNotFoundError(str(project_id))

    db_metrics = MetricsDB(
        project_id=str(project_id),
        period_start=metrics.period_start,
        period_end=metrics.period_end,
        jira_defects=metrics.jira_defects or {},
        flow_metrics=metrics.flow_metrics or {},
        github_metrics=metrics.github_metrics or {},
        sev1_incident=metrics.sev1_incident,
        milestone_data=metrics.milestone_data or {},
        governance_status=metrics.governance_status or {},
    )
    db.add(db_metrics)
    await db.flush()
    await db.refresh(db_metrics)
    return Metrics.model_validate(db_metrics)


@router.get("/{metrics_id}", response_model=Metrics)
@limiter.limit("100/minute")
async def get_metrics(
    request: Request, metrics_id: UUID, current_user: CurrentUser, db: DBSession
) -> Metrics:
    """Get specific metrics by ID. Requires authentication."""
    result = await db.execute(
        select(MetricsDB).where(MetricsDB.id == str(metrics_id))
    )
    metrics = result.scalar_one_or_none()
    if metrics is None:
        raise MetricsNotFoundError(str(metrics_id))
    return Metrics.model_validate(metrics)


@router.delete("/{metrics_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_metrics(
    request: Request, metrics_id: UUID, current_user: CurrentUser, db: DBSession
) -> None:
    """Delete metrics by ID. Requires authentication."""
    result = await db.execute(
        select(MetricsDB).where(MetricsDB.id == str(metrics_id))
    )
    metrics = result.scalar_one_or_none()
    if metrics is None:
        raise MetricsNotFoundError(str(metrics_id))
    await db.delete(metrics)
