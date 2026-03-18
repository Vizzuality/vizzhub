"""Report CRUD endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.schemas.report import (
    ReportCreate,
    ReportResponse,
    ReportUpdate,
    ReportWithPartsResponse,
)
from app.modules.tracker.api.enrichment import enrich_part, enrich_report
from app.modules.tracker.api.helpers import get_or_404

router = APIRouter()


async def _prepopulate_parts(report: ReportDB, db: AsyncSession) -> None:
    """Copy report_part structure from the user's most recent previous period."""
    current_period = await db.execute(
        select(ReportingPeriodDB).where(
            ReportingPeriodDB.id == report.reporting_period_id
        )
    )
    period = current_period.scalar_one_or_none()
    if not period:
        return

    prev_period_result = await db.execute(
        select(ReportingPeriodDB)
        .where(ReportingPeriodDB.date < period.date)
        .order_by(ReportingPeriodDB.date.desc())
        .limit(1)
    )
    prev_period = prev_period_result.scalar_one_or_none()
    if not prev_period:
        return

    prev_report_result = await db.execute(
        select(ReportDB).where(
            ReportDB.user_id == report.user_id,
            ReportDB.reporting_period_id == prev_period.id,
        )
    )
    prev_report = prev_report_result.scalar_one_or_none()
    if not prev_report:
        return

    prev_parts_result = await db.execute(
        select(ReportPartDB).where(ReportPartDB.report_id == prev_report.id)
    )
    for prev_part in prev_parts_result.scalars().all():
        new_part = ReportPartDB(
            report_id=report.id,
            project_id=prev_part.project_id,
            functional_area_id=prev_part.functional_area_id,
            percentage=None,
            cost=None,
            days=None,
        )
        db.add(new_part)
    await db.flush()



@router.get("")
async def list_reports(
    reporting_period_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> list[ReportResponse]:
    result = await db.execute(
        select(ReportDB)
        .where(ReportDB.reporting_period_id == reporting_period_id)
        .order_by(ReportDB.created_at)
    )
    reports = result.scalars().all()
    return [await enrich_report(r, db) for r in reports]


@router.post("", status_code=201)
async def create_report(
    data: ReportCreate,
    db: DBSession,
    user: CurrentUser,
) -> ReportResponse:
    report = ReportDB(
        user_id=UUID(user.user_id),
        reporting_period_id=data.reporting_period_id,
        estimated=data.estimated,
    )
    db.add(report)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Report already exists for this user and period",
        )

    await _prepopulate_parts(report, db)
    await db.commit()
    await db.refresh(report)
    return await enrich_report(report, db)


@router.get("/{report_id}")
async def get_report(
    report_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ReportWithPartsResponse:
    report = await get_or_404(ReportDB, report_id, db, "Report")

    enriched = await enrich_report(report, db)

    parts_result = await db.execute(
        select(ReportPartDB)
        .where(ReportPartDB.report_id == report_id)
        .order_by(ReportPartDB.created_at)
    )
    parts = [await enrich_part(p, db) for p in parts_result.scalars().all()]

    return ReportWithPartsResponse(
        **enriched.model_dump(),
        parts=parts,
    )


@router.put("/{report_id}")
async def update_report(
    report_id: UUID,
    data: ReportUpdate,
    db: DBSession,
    user: CurrentUser,
) -> ReportResponse:
    report = await get_or_404(ReportDB, report_id, db, "Report")
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(report, field, value)
    await db.commit()
    await db.refresh(report)
    return await enrich_report(report, db)


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> None:
    report = await get_or_404(ReportDB, report_id, db, "Report")
    await db.delete(report)
    await db.commit()
