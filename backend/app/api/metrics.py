"""Metrics input endpoints."""

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import DBSession
from app.core.exceptions import MetricsNotFoundError, ProjectNotFoundError
from app.models.metrics import Metrics, MetricsCreate, MetricsDB
from app.models.project import ProjectDB

router = APIRouter()


@router.get("/project/{project_id}", response_model=list[Metrics])
async def list_project_metrics(project_id: UUID, db: DBSession) -> list[Metrics]:
    """List all metrics for a project."""
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


@router.post(
    "/project/{project_id}",
    response_model=Metrics,
    status_code=status.HTTP_201_CREATED,
)
async def create_metrics(
    project_id: UUID,
    metrics: MetricsCreate,
    db: DBSession,
) -> Metrics:
    """Create or update metrics for a project and period."""
    result = await db.execute(
        select(ProjectDB).where(ProjectDB.id == str(project_id))
    )
    if result.scalar_one_or_none() is None:
        raise ProjectNotFoundError(str(project_id))

    db_metrics = MetricsDB(
        project_id=str(project_id),
        period_start=metrics.period_start,
        period_end=metrics.period_end,
        evm_data=metrics.evm_data.model_dump() if metrics.evm_data else None,
        milestones=[m.model_dump() for m in metrics.milestones] if metrics.milestones else None,
        jira_defects=metrics.jira_defects.model_dump() if metrics.jira_defects else None,
        flow_metrics=metrics.flow_metrics.model_dump() if metrics.flow_metrics else None,
        github_metrics=metrics.github_metrics.model_dump() if metrics.github_metrics else None,
        test_maturity=metrics.test_maturity.model_dump() if metrics.test_maturity else None,
        architecture=metrics.architecture.model_dump() if metrics.architecture else None,
        pm_satisfaction=metrics.pm_satisfaction.model_dump() if metrics.pm_satisfaction else None,
        client_survey=metrics.client_survey.model_dump() if metrics.client_survey else None,
        strategic_impact=metrics.strategic_impact.value if metrics.strategic_impact else None,
        governance_exceptions=metrics.governance_exceptions,
        sev1_incident=metrics.sev1_incident,
    )

    db.add(db_metrics)
    await db.flush()
    await db.refresh(db_metrics)
    return Metrics.model_validate(db_metrics)


@router.get("/{metrics_id}", response_model=Metrics)
async def get_metrics(metrics_id: UUID, db: DBSession) -> Metrics:
    """Get metrics by ID."""
    result = await db.execute(
        select(MetricsDB).where(MetricsDB.id == str(metrics_id))
    )
    metrics = result.scalar_one_or_none()
    if metrics is None:
        raise MetricsNotFoundError(str(metrics_id))
    return Metrics.model_validate(metrics)


@router.get("/project/{project_id}/latest", response_model=Metrics)
async def get_latest_metrics(project_id: UUID, db: DBSession) -> Metrics:
    """Get the latest metrics for a project."""
    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.period_end.desc())
        .limit(1)
    )
    metrics = result.scalar_one_or_none()
    if metrics is None:
        raise MetricsNotFoundError(str(project_id))
    return Metrics.model_validate(metrics)
