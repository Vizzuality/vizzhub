"""Progress report CRUD endpoints."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.progress_report import ProgressReportDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.schemas.progress_report import (
    BatchProgressResponse,
    ProgressReportCreate,
    ProgressReportResponse,
    ProgressReportUpdate,
    ProgressSummary,
)

from fastapi import APIRouter, HTTPException

router = APIRouter()


async def _previous_percentage(
    db, project_id: UUID, current_period_id: UUID,
) -> Decimal | None:
    """Get the percentage from the most recent prior period for this project."""
    current_period = await db.get(ReportingPeriodDB, current_period_id)
    if not current_period:
        return None

    stmt = (
        select(ProgressReportDB.percentage)
        .join(ReportingPeriodDB)
        .where(
            ProgressReportDB.project_id == project_id,
            ReportingPeriodDB.date < current_period.date,
        )
        .order_by(ReportingPeriodDB.date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _to_response(
    pr: ProgressReportDB, period_date: str | None = None,
) -> ProgressReportResponse:
    return ProgressReportResponse(
        id=pr.id,
        reporting_period_id=pr.reporting_period_id,
        project_id=pr.project_id,
        period_date=period_date,
        percentage=float(pr.percentage * 100),
        delta=float(pr.delta * 100) if pr.delta is not None else None,
    )


@router.get("/{project_id}/progress")
async def list_progress(
    project_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> list[ProgressReportResponse]:
    stmt = (
        select(ProgressReportDB, ReportingPeriodDB.date)
        .join(ReportingPeriodDB)
        .where(ProgressReportDB.project_id == project_id)
        .order_by(ReportingPeriodDB.date.asc())
    )
    result = await db.execute(stmt)
    return [_to_response(pr, str(d)) for pr, d in result.all()]


@router.post(
    "/{project_id}/progress",
    status_code=201,
    responses={409: {"description": "Progress already exists for this period"}},
)
async def create_progress(
    project_id: UUID,
    body: ProgressReportCreate,
    db: DBSession,
    user: CurrentUser,
) -> ProgressReportResponse:
    pct = Decimal(str(body.percentage)) / Decimal("100")
    prev = await _previous_percentage(db, project_id, body.reporting_period_id)
    delta = pct - prev if prev is not None else pct

    pr = ProgressReportDB(
        reporting_period_id=body.reporting_period_id,
        project_id=project_id,
        percentage=pct,
        delta=delta,
    )
    db.add(pr)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Progress already exists for this project/period")
    await db.refresh(pr)

    period = await db.get(ReportingPeriodDB, pr.reporting_period_id)
    return _to_response(pr, str(period.date) if period else None)


@router.put("/{project_id}/progress/{progress_id}")
async def update_progress(
    project_id: UUID,
    progress_id: UUID,
    body: ProgressReportUpdate,
    db: DBSession,
    user: CurrentUser,
) -> ProgressReportResponse:
    pr = await db.get(ProgressReportDB, progress_id)
    if not pr or pr.project_id != project_id:
        raise HTTPException(404, "Progress report not found")

    pct = Decimal(str(body.percentage)) / Decimal("100")
    prev = await _previous_percentage(db, project_id, pr.reporting_period_id)
    delta = pct - prev if prev is not None else pct

    pr.percentage = pct
    pr.delta = delta
    await db.commit()
    await db.refresh(pr)

    period = await db.get(ReportingPeriodDB, pr.reporting_period_id)
    return _to_response(pr, str(period.date) if period else None)


@router.delete("/{project_id}/progress/{progress_id}", status_code=204)
async def delete_progress(
    project_id: UUID,
    progress_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> None:
    pr = await db.get(ProgressReportDB, progress_id)
    if not pr or pr.project_id != project_id:
        raise HTTPException(404, "Progress report not found")
    await db.delete(pr)
    await db.commit()


@router.post("/batch-progress")
async def batch_progress(
    body: dict,
    db: DBSession,
    user: CurrentUser,
) -> BatchProgressResponse:
    """Get latest progress for multiple projects."""
    project_ids = [UUID(pid) for pid in body.get("project_ids", [])]
    if not project_ids:
        return BatchProgressResponse(progress={})

    # For each project, get the progress report from the latest period
    stmt = (
        select(
            ProgressReportDB.project_id,
            ProgressReportDB.percentage,
            ProgressReportDB.delta,
        )
        .join(ReportingPeriodDB)
        .where(ProgressReportDB.project_id.in_(project_ids))
        .distinct(ProgressReportDB.project_id)
        .order_by(
            ProgressReportDB.project_id,
            ReportingPeriodDB.date.desc(),
        )
    )
    result = await db.execute(stmt)

    progress: dict[str, ProgressSummary] = {}
    for pid, pct, delta in result.all():
        progress[str(pid)] = ProgressSummary(
            project_id=pid,
            percentage=float(pct * 100),
            delta=float(delta * 100) if delta is not None else None,
        )

    return BatchProgressResponse(progress=progress)
