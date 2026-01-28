"""Snapshot endpoints for historical metrics."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, get_project_or_404, limiter
from app.models.snapshot import SnapshotCreate, SnapshotResponse
from app.services.snapshot_service import SnapshotService

router = APIRouter()


@router.post(
    "/project/{project_id}",
    response_model=SnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("10/minute")
async def create_snapshot(
    request: Request,
    project_id: UUID,
    data: SnapshotCreate,
    current_user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
) -> SnapshotResponse:
    """Create a snapshot for a specific month (manual trigger).

    Creates a consolidated metrics record from all metrics in the period
    and links it to the snapshot with the current config (weights/targets).
    """
    await get_project_or_404(db, project_id)

    existing = await SnapshotService.get_snapshot(
        db, project_id, data.period_year, data.period_month
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Snapshot already exists for {data.period_year}-{data.period_month:02d}",
        )

    try:
        snapshot = await SnapshotService.create_snapshot(
            db, project_id, data.period_year, data.period_month, config
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return SnapshotResponse.from_db(snapshot)


@router.get("/project/{project_id}", response_model=list[SnapshotResponse])
@limiter.limit("100/minute")
async def get_project_snapshots(
    request: Request,
    project_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = 12,
) -> list[SnapshotResponse]:
    """Get snapshot history for a project."""
    await get_project_or_404(db, project_id)

    snapshots = await SnapshotService.get_project_history(db, project_id, limit)
    return [SnapshotResponse.from_db(s) for s in snapshots]


@router.get("/project/{project_id}/{year}/{month}", response_model=SnapshotResponse)
@limiter.limit("100/minute")
async def get_snapshot(
    request: Request,
    project_id: UUID,
    year: int,
    month: int,
    current_user: CurrentUser,
    db: DBSession,
) -> SnapshotResponse:
    """Get a specific snapshot by project and period."""
    await get_project_or_404(db, project_id)

    snapshot = await SnapshotService.get_snapshot(db, project_id, year, month)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot not found for {year}-{month:02d}",
        )

    return SnapshotResponse.from_db(snapshot)


@router.delete("/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_snapshot(
    request: Request,
    snapshot_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
) -> None:
    """Delete a snapshot and its consolidated metrics."""
    deleted = await SnapshotService.delete_snapshot(db, snapshot_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found",
        )
