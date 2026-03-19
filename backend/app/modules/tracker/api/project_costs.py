"""Project cost aggregation endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.schemas.aggregation import AggregationResponse
from app.modules.tracker.schemas.project_cost import (
    BatchCostsRequest,
    BatchCostsResponse,
    ProjectCostSummary,
    ProjectCostSummaryLite,
    ProjectReportPartResponse,
)
from app.modules.tracker.services.aggregation_service import (
    ALLOWED_GROUP_BY,
    get_batch_cost_summaries,
    get_project_aggregations,
    get_project_cost_summary,
    get_project_report_parts,
)

router = APIRouter()


@router.post(
    "/batch-costs",
    responses={422: {"description": "Invalid UUID in project_ids"}},
)
async def batch_project_costs(
    body: BatchCostsRequest,
    db: DBSession,
    user: CurrentUser,
) -> BatchCostsResponse:
    try:
        uuids = [UUID(pid) for pid in body.project_ids]
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid UUID: {e}")

    summaries = await get_batch_cost_summaries(db, uuids)

    results: dict[str, ProjectCostSummaryLite] = {}
    for pid_uuid, summary in summaries.items():
        results[str(pid_uuid)] = summary

    return BatchCostsResponse(costs=results, errors={})


@router.get("/{project_id}/aggregations")
async def project_aggregations(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
    group_by: Annotated[str, Query()],
) -> AggregationResponse:
    if group_by not in ALLOWED_GROUP_BY:
        raise HTTPException(
            status_code=400,
            detail=f"group_by must be one of: {', '.join(sorted(ALLOWED_GROUP_BY))}",
        )
    return await get_project_aggregations(db, project_id, group_by)


@router.get("/{project_id}/cost-summary")
async def project_cost_summary(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ProjectCostSummary:
    return await get_project_cost_summary(db, project_id)


@router.get("/{project_id}/report-parts")
async def project_report_parts(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
    period_id: Annotated[UUID | None, Query()] = None,
) -> list[ProjectReportPartResponse]:
    return await get_project_report_parts(db, project_id, period_id)
