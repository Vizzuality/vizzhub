"""Reporting period management with state machine."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.reporting_period import (
    ReportingPeriodDB,
    ReportingPeriodStatus,
)
from app.modules.tracker.schemas.reporting_period import (
    ReportingPeriodCreate,
    ReportingPeriodUpdate,
)

VALID_TRANSITIONS = {
    ReportingPeriodStatus.UNSTARTED: {ReportingPeriodStatus.ACTIVE},
    ReportingPeriodStatus.ACTIVE: {ReportingPeriodStatus.FINISHED},
    ReportingPeriodStatus.FINISHED: {ReportingPeriodStatus.ACTIVE},
}


async def get_periods(db: AsyncSession) -> list[ReportingPeriodDB]:
    result = await db.execute(
        select(ReportingPeriodDB).order_by(ReportingPeriodDB.date.desc())
    )
    return list(result.scalars().all())


async def get_period(period_id: UUID, db: AsyncSession) -> ReportingPeriodDB:
    result = await db.execute(
        select(ReportingPeriodDB).where(ReportingPeriodDB.id == period_id)
    )
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporting period {period_id} not found",
        )
    return period


async def create_period(
    data: ReportingPeriodCreate, db: AsyncSession,
) -> ReportingPeriodDB:
    period = ReportingPeriodDB(
        date=data.date,
        base_rate=data.base_rate,
        status=ReportingPeriodStatus.UNSTARTED.value,
    )
    db.add(period)
    await db.flush()
    await db.refresh(period)
    return period


async def update_period(
    period_id: UUID, data: ReportingPeriodUpdate, db: AsyncSession,
) -> ReportingPeriodDB:
    period = await get_period(period_id, db)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(period, field, value)
    await db.flush()
    await db.refresh(period)
    return period


async def delete_period(period_id: UUID, db: AsyncSession) -> None:
    period = await get_period(period_id, db)

    report_count_result = await db.execute(
        select(func.count()).select_from(ReportDB).where(
            ReportDB.reporting_period_id == period_id
        )
    )
    if report_count_result.scalar() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete period with existing reports",
        )

    await db.delete(period)
    await db.flush()


async def _deactivate_current_active(db: AsyncSession) -> None:
    """Set any currently active period to finished."""
    result = await db.execute(
        select(ReportingPeriodDB).where(
            ReportingPeriodDB.status == ReportingPeriodStatus.ACTIVE.value
        )
    )
    active_period = result.scalar_one_or_none()
    if active_period:
        active_period.status = ReportingPeriodStatus.FINISHED.value


async def _transition_period(
    period_id: UUID, target_status: ReportingPeriodStatus, db: AsyncSession,
) -> ReportingPeriodDB:
    """Apply a state transition with validation."""
    period = await get_period(period_id, db)
    current = ReportingPeriodStatus(period.status)

    if target_status not in VALID_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition: {current.value} → {target_status.value}",
        )

    if target_status == ReportingPeriodStatus.ACTIVE:
        await _deactivate_current_active(db)

    period.status = target_status.value
    await db.flush()
    await db.refresh(period)
    return period


async def activate_period(
    period_id: UUID, db: AsyncSession,
) -> ReportingPeriodDB:
    return await _transition_period(
        period_id, ReportingPeriodStatus.ACTIVE, db,
    )


async def finish_period(
    period_id: UUID, db: AsyncSession,
) -> ReportingPeriodDB:
    return await _transition_period(
        period_id, ReportingPeriodStatus.FINISHED, db,
    )


