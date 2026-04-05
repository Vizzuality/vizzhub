"""Report part CRUD endpoints with auto-calculated cost/days."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession, OptionalScoreCache
from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.tracker.api.enrichment import enrich_part, enrich_parts_batch
from app.modules.tracker.api.helpers import get_or_404, refresh_scorecard_evm
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.schemas.report_part import (
    ReportPartCreate,
    ReportPartResponse,
    ReportPartUpdate,
)
from app.modules.tracker.services.cost_service import apply_cost_and_days

OwnReportManager = Annotated[TokenData, Depends(require_permission(Action.TRACKER_MANAGE_OWN_REPORTS))]

router = APIRouter()

REPORT_PART_LABEL = "Report part"


@router.get("")
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
    return await enrich_parts_batch(list(result.scalars().all()), db)


@router.post("", status_code=201)
async def create_report_part(
    data: ReportPartCreate,
    db: DBSession,
    user: OwnReportManager,
    cache: OptionalScoreCache,
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
    await refresh_scorecard_evm(db, part.project_id, score_cache=cache)
    return await enrich_part(part, db)


@router.get("/{part_id}")
async def get_report_part(
    part_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ReportPartResponse:
    part = await get_or_404(ReportPartDB, part_id, db, REPORT_PART_LABEL)
    return await enrich_part(part, db)


@router.put("/{part_id}")
async def update_report_part(
    part_id: UUID,
    data: ReportPartUpdate,
    db: DBSession,
    user: OwnReportManager,
    cache: OptionalScoreCache,
) -> ReportPartResponse:
    part = await get_or_404(ReportPartDB, part_id, db, REPORT_PART_LABEL)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(part, field, value)

    part = await apply_cost_and_days(part, db)
    await db.commit()
    await db.refresh(part)
    await refresh_scorecard_evm(db, part.project_id, score_cache=cache)
    return await enrich_part(part, db)


@router.delete("/{part_id}", status_code=204)
async def delete_report_part(
    part_id: UUID,
    db: DBSession,
    user: OwnReportManager,
    cache: OptionalScoreCache,
) -> None:
    part = await get_or_404(ReportPartDB, part_id, db, REPORT_PART_LABEL)
    project_id = part.project_id
    await db.delete(part)
    await db.commit()
    await refresh_scorecard_evm(db, project_id, score_cache=cache)
