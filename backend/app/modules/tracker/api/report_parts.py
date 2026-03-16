"""Report part CRUD endpoints with auto-calculated cost/days."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.schemas.report_part import (
    ReportPartCreate,
    ReportPartResponse,
    ReportPartUpdate,
)
from app.modules.tracker.services.cost_service import apply_cost_and_days
from app.modules.tracker.api.enrichment import enrich_part

router = APIRouter()


async def _get_part_or_404(part_id: UUID, db: AsyncSession) -> ReportPartDB:
    result = await db.execute(
        select(ReportPartDB).where(ReportPartDB.id == part_id)
    )
    part = result.scalar_one_or_none()
    if not part:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report part {part_id} not found",
        )
    return part


@router.get("", response_model=list[ReportPartResponse])
async def list_report_parts(
    report_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> list[ReportPartResponse]:
    result = await db.execute(
        select(ReportPartDB)
        .where(ReportPartDB.report_id == report_id)
        .order_by(ReportPartDB.created_at)
    )
    return [await enrich_part(p, db) for p in result.scalars().all()]


@router.post("", response_model=ReportPartResponse, status_code=201)
async def create_report_part(
    data: ReportPartCreate,
    db: DBSession,
    user: CurrentUser,
) -> ReportPartResponse:
    part = ReportPartDB(
        report_id=data.report_id,
        project_id=data.project_id,
        functional_area_id=data.functional_area_id,
        percentage=data.percentage,
    )
    db.add(part)
    await db.flush()

    part = await apply_cost_and_days(part, db)
    await db.commit()
    await db.refresh(part)
    return await enrich_part(part, db)


@router.get("/{part_id}", response_model=ReportPartResponse)
async def get_report_part(
    part_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ReportPartResponse:
    part = await _get_part_or_404(part_id, db)
    return await enrich_part(part, db)


@router.put("/{part_id}", response_model=ReportPartResponse)
async def update_report_part(
    part_id: UUID,
    data: ReportPartUpdate,
    db: DBSession,
    user: CurrentUser,
) -> ReportPartResponse:
    part = await _get_part_or_404(part_id, db)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(part, field, value)

    part = await apply_cost_and_days(part, db)
    await db.commit()
    await db.refresh(part)
    return await enrich_part(part, db)


@router.delete("/{part_id}", status_code=204)
async def delete_report_part(
    part_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> None:
    part = await _get_part_or_404(part_id, db)
    await db.delete(part)
    await db.commit()
