"""XLSX export endpoints."""

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, get_project_or_404, limiter
from app.models.metrics import SnapshotType
from app.modules.scorecard.services.export_service import ExportService

MAX_EXPORT_MONTHS = 60

router = APIRouter()

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _parse_month_param(value: str) -> tuple[int, int]:
    """Parse 'YYYY-MM' string to (year, month) tuple."""
    match = re.match(r"^(\d{4})-(\d{2})$", value)
    if not match:
        raise HTTPException(
            status_code=400, detail=f"Invalid date format: {value}. Use YYYY-MM."
        )
    year, month = int(match.group(1)), int(match.group(2))
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=400, detail=f"Invalid month: {month}. Must be 01-12."
        )
    return year, month


def _validate_date_range(
    start_year: int, start_month: int, end_year: int, end_month: int
) -> None:
    """Validate that end >= start and range does not exceed MAX_EXPORT_MONTHS."""
    if (end_year, end_month) < (start_year, start_month):
        raise HTTPException(
            status_code=400, detail="End period must not be before start period."
        )
    months = (end_year - start_year) * 12 + (end_month - start_month) + 1
    if months > MAX_EXPORT_MONTHS:
        raise HTTPException(
            status_code=400,
            detail=f"Date range exceeds maximum of {MAX_EXPORT_MONTHS} months.",
        )


def _sanitize_filename(name: str) -> str:
    """Sanitize project name for use in filename."""
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


@router.get("/project/{project_id}", responses={400: {"description": "Bad request"}})
@limiter.limit("10/minute")
async def export_project_detail(
    request: Request,
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    start: Annotated[str, Query(description="Start period (YYYY-MM)")],
    end: Annotated[str, Query(description="End period (YYYY-MM)")],
    snapshot_type: Annotated[SnapshotType, Query(description="cumulative or punctual")] = SnapshotType.CUMULATIVE,
) -> Response:
    """Export project scorecard data to XLSX."""
    project = await get_project_or_404(db, project_id)
    start_year, start_month = _parse_month_param(start)
    end_year, end_month = _parse_month_param(end)
    _validate_date_range(start_year, start_month, end_year, end_month)

    service = ExportService(config)
    output = await service.export_project_detail(
        db=db,
        project=project,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
        snapshot_type=snapshot_type.value,
    )

    filename = f"{_sanitize_filename(project.name)}_scorecard_{start}_{end}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/global", responses={400: {"description": "Bad request"}})
@limiter.limit("10/minute")
async def export_global_dashboard(
    request: Request,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    start: Annotated[str, Query(description="Start period (YYYY-MM)")],
    end: Annotated[str, Query(description="End period (YYYY-MM)")],
    snapshot_type: Annotated[SnapshotType, Query(description="cumulative or punctual")] = SnapshotType.CUMULATIVE,
) -> Response:
    """Export global dashboard data to XLSX."""
    start_year, start_month = _parse_month_param(start)
    end_year, end_month = _parse_month_param(end)
    _validate_date_range(start_year, start_month, end_year, end_month)

    service = ExportService(config)
    output = await service.export_global_dashboard(
        db=db,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
        snapshot_type=snapshot_type.value,
    )

    filename = f"global_scorecard_{start}_{end}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
