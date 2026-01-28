"""Metrics input endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DBSession, get_project_or_404, limiter
from app.core.exceptions import MetricsNotFoundError
from app.models.metrics import Metrics, MetricsCreate, MetricsDB

router = APIRouter()


@router.get("/project/{project_id}", response_model=list[Metrics])
@limiter.limit("100/minute")
async def list_project_metrics(
    request: Request, project_id: UUID, current_user: CurrentUser, db: DBSession
) -> list[Metrics]:
    """List all metrics for a project. Requires authentication."""
    await get_project_or_404(db, project_id)

    result = await db.execute(
        select(MetricsDB)
        .where(MetricsDB.project_id == str(project_id))
        .order_by(MetricsDB.period_end.desc())
    )
    metrics_list = result.scalars().all()
    return [Metrics.from_db(m) for m in metrics_list]


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
    project = await get_project_or_404(db, project_id)

    # For finished projects, only allow end-of-project metrics
    if project.status == "finished":
        metrics_dict = metrics.model_dump(exclude_unset=True)
        allowed_fields = {"period_start", "period_end", "strategic_impact", "client_survey", "sev1_incident"}
        provided_fields = set(metrics_dict.keys())
        disallowed = provided_fields - allowed_fields

        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project is finished. Only end-of-project metrics (strategic_impact, client_survey) can be updated. Disallowed fields: {sorted(disallowed)}",
            )

    db_data = metrics.to_db_dict()
    db_data["project_id"] = str(project_id)

    db_metrics = MetricsDB(**db_data)
    db.add(db_metrics)
    await db.flush()
    await db.refresh(db_metrics)
    return Metrics.from_db(db_metrics)


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
    return Metrics.from_db(metrics)


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
