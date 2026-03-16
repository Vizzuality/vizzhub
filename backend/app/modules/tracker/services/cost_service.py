"""Cost and days calculation for report parts."""

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.rate import RateDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.constants import DEFAULT_RATE
from app.modules.tracker.models.project_settings import TrackerProjectSettingsDB
WORKING_DAYS_PER_MONTH = Decimal("20")


def _calculate_days(percentage: Decimal, dedication: Decimal) -> Decimal:
    """Calculate working days from percentage and dedication."""
    return percentage * WORKING_DAYS_PER_MONTH * dedication


def calculate_cost_and_days(
    percentage: Decimal,
    rate_value: Decimal,
    dedication: Decimal,
    contract_rate: Decimal,
    base_rate: Decimal,
) -> tuple[Decimal, Decimal]:
    """Calculate cost and days for a report part.

    cost = percentage × rate_value × dedication × (contract_rate / base_rate)
    days = percentage / 5.0 × dedication
    """
    rate_multiplier = contract_rate / base_rate
    cost = percentage * rate_value * dedication * rate_multiplier
    days = _calculate_days(percentage, dedication)
    return cost, days


async def apply_cost_and_days(
    report_part: ReportPartDB,
    db: AsyncSession,
) -> ReportPartDB:
    """Resolve related entities and calculate cost/days for a report part."""
    if report_part.percentage is None:
        report_part.cost = None
        report_part.days = None
        return report_part

    report_result = await db.execute(
        select(ReportDB).where(ReportDB.id == report_part.report_id)
    )
    report = report_result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_part.report_id} not found",
        )

    user_result = await db.execute(
        select(UserDB).where(UserDB.id == report.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {report.user_id} not found",
        )

    if not user.rate_id or not user.dedication:
        report_part.cost = None
        report_part.days = _calculate_days(
            report_part.percentage, user.dedication or Decimal("1.0")
        )
        return report_part

    rate_result = await db.execute(
        select(RateDB).where(RateDB.id == user.rate_id)
    )
    rate = rate_result.scalar_one_or_none()
    if not rate:
        report_part.cost = None
        report_part.days = _calculate_days(report_part.percentage, user.dedication)
        return report_part

    period_result = await db.execute(
        select(ReportingPeriodDB).where(
            ReportingPeriodDB.id == report.reporting_period_id
        )
    )
    period = period_result.scalar_one()

    settings_result = await db.execute(
        select(TrackerProjectSettingsDB).where(
            TrackerProjectSettingsDB.project_id == report_part.project_id
        )
    )
    settings = settings_result.scalar_one_or_none()
    contract_rate = settings.contract_rate if settings else DEFAULT_RATE

    cost, days = calculate_cost_and_days(
        percentage=report_part.percentage,
        rate_value=rate.value,
        dedication=user.dedication,
        contract_rate=contract_rate,
        base_rate=period.base_rate,
    )

    report_part.cost = cost
    report_part.days = days
    return report_part
