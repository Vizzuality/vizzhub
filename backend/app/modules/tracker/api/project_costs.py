"""Project cost aggregation endpoints."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.schemas.project_cost import (
    ProjectCostSummary,
    ProjectReportPartResponse,
)
from app.modules.tracker.services.aggregation_service import (
    get_project_cost_summary,
    get_project_report_parts,
)

router = APIRouter()


@router.get("/{project_id}/cost-summary", response_model=ProjectCostSummary)
async def project_cost_summary(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ProjectCostSummary:
    return await get_project_cost_summary(db, project_id)


@router.get(
    "/{project_id}/report-parts",
    response_model=list[ProjectReportPartResponse],
)
async def project_report_parts(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
    period_id: UUID | None = Query(default=None),
) -> list[ProjectReportPartResponse]:
    return await get_project_report_parts(db, project_id, period_id)
