"""Report CRUD endpoints."""

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.core.auth import TokenData
from app.core.models.project import ProjectDB, ProjectStatus
from app.core.models.user import UserDB
from app.core.permissions import Action, require_permission
from app.modules.tracker.api.enrichment import (
    enrich_parts_batch,
    enrich_report,
    enrich_reports_batch,
)
from app.modules.tracker.api.helpers import get_or_404
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.schemas.report import (
    ReportCreate,
    ReportResponse,
    ReportUpdate,
    ReportWithPartsResponse,
)

OwnReportManager = Annotated[TokenData, Depends(require_permission(Action.TRACKER_MANAGE_OWN_REPORTS))]

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
        select(ReportPartDB)
        .join(ProjectDB, ReportPartDB.project_id == ProjectDB.id)
        .where(ReportPartDB.report_id == prev_report.id)
        .where(ReportPartDB.percentage > 0)
        .where(ProjectDB.status != ProjectStatus.FINISHED)
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
        .join(UserDB, ReportDB.user_id == UserDB.id)
        .where(
            ReportDB.reporting_period_id == reporting_period_id,
            UserDB.requires_project_reporting.is_(True),
        )
        .order_by(ReportDB.created_at)
    )
    reports = result.scalars().all()
    return await enrich_reports_batch(list(reports), db)


@router.post("", status_code=201)
async def create_report(
    data: ReportCreate,
    db: DBSession,
    user: OwnReportManager,
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
    parts = await enrich_parts_batch(
        list(parts_result.scalars().all()), db,
    )

    return ReportWithPartsResponse(
        **enriched.model_dump(),
        parts=parts,
    )


@router.put("/{report_id}")
async def update_report(
    report_id: UUID,
    data: ReportUpdate,
    db: DBSession,
    user: OwnReportManager,
) -> ReportResponse:
    report = await get_or_404(ReportDB, report_id, db, "Report")
    update_data = data.model_dump(exclude_unset=True)

    is_confirming = (
        update_data.get("estimated") is False and report.estimated is True
    )
    if is_confirming:
        parts_result = await db.execute(
            select(ReportPartDB.percentage).where(
                ReportPartDB.report_id == report_id
            )
        )
        total = sum(p or 0 for (p,) in parts_result.all())
        if not math.isclose(float(total), 1.0, rel_tol=1e-4):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Report percentages must total 100% to confirm. Current total: {round(float(total) * 100, 1)}%",
            )

    for field, value in update_data.items():
        setattr(report, field, value)
    await db.commit()
    await db.refresh(report)
    return await enrich_report(report, db)


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: UUID,
    db: DBSession,
    user: OwnReportManager,
) -> None:
    report = await get_or_404(ReportDB, report_id, db, "Report")
    await db.delete(report)
    await db.commit()
