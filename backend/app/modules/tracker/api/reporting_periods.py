"""Reporting periods CRUD and state transition endpoints."""

from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.api.deps import CurrentUser, DBSession
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.schemas.reporting_period import (
    ReportingPeriodCreate,
    ReportingPeriodResponse,
    ReportingPeriodUpdate,
)
from app.modules.tracker.services import period_service

router = APIRouter()


@router.get("")
async def list_periods(
    db: DBSession,
    user: CurrentUser,
) -> list[ReportingPeriodResponse]:
    periods = await period_service.get_periods(db)
    period_ids = [p.id for p in periods]
    counts: dict[str, int] = {}
    if period_ids:
        result = await db.execute(
            select(
                ReportDB.reporting_period_id,
                func.count(ReportDB.id),
            )
            .where(ReportDB.reporting_period_id.in_(period_ids))
            .group_by(ReportDB.reporting_period_id)
        )
        counts = {str(row[0]): row[1] for row in result.all()}
    responses = []
    for p in periods:
        resp = ReportingPeriodResponse.model_validate(p)
        resp.report_count = counts.get(str(p.id), 0)
        responses.append(resp)
    return responses


@router.post("", status_code=201)
async def create_period(
    data: ReportingPeriodCreate,
    db: DBSession,
    user: CurrentUser,
) -> ReportingPeriodResponse:
    period = await period_service.create_period(data, db)
    await db.commit()
    await db.refresh(period)
    return ReportingPeriodResponse.model_validate(period)


@router.get("/{period_id}")
async def get_period(
    period_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ReportingPeriodResponse:
    period = await period_service.get_period(period_id, db)
    return ReportingPeriodResponse.model_validate(period)


@router.put("/{period_id}")
async def update_period(
    period_id: UUID,
    data: ReportingPeriodUpdate,
    db: DBSession,
    user: CurrentUser,
) -> ReportingPeriodResponse:
    period = await period_service.update_period(period_id, data, db)
    await db.commit()
    await db.refresh(period)
    return ReportingPeriodResponse.model_validate(period)


@router.delete("/{period_id}", status_code=204)
async def delete_period(
    period_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> None:
    await period_service.delete_period(period_id, db)
    await db.commit()


@router.post("/{period_id}/activate")
async def activate_period(
    period_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ReportingPeriodResponse:
    period = await period_service.activate_period(period_id, db)
    await db.commit()
    await db.refresh(period)
    return ReportingPeriodResponse.model_validate(period)


@router.post("/{period_id}/finish")
async def finish_period(
    period_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ReportingPeriodResponse:
    period = await period_service.finish_period(period_id, db)
    await db.commit()
    await db.refresh(period)
    return ReportingPeriodResponse.model_validate(period)


@router.post("/{period_id}/reactivate")
async def reactivate_period(
    period_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> ReportingPeriodResponse:
    period = await period_service.activate_period(period_id, db)
    await db.commit()
    await db.refresh(period)
    return ReportingPeriodResponse.model_validate(period)
