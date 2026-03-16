"""Shared enrichment helpers for tracker API responses."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.schemas.report import ReportResponse
from app.modules.tracker.schemas.report_part import ReportPartResponse


async def enrich_report(report: ReportDB, db: AsyncSession) -> ReportResponse:
    """Add user_name and user_email to a report response."""
    user_result = await db.execute(
        select(UserDB).where(UserDB.id == report.user_id)
    )
    report_user = user_result.scalar_one_or_none()
    return ReportResponse(
        id=report.id,
        user_id=report.user_id,
        reporting_period_id=report.reporting_period_id,
        estimated=report.estimated,
        user_name=report_user.name if report_user else None,
        user_email=report_user.email if report_user else None,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


async def enrich_part(part: ReportPartDB, db: AsyncSession) -> ReportPartResponse:
    """Add project_name to a report part response."""
    project_result = await db.execute(
        select(ProjectDB).where(ProjectDB.id == part.project_id)
    )
    project = project_result.scalar_one_or_none()
    return ReportPartResponse(
        id=part.id,
        report_id=part.report_id,
        project_id=part.project_id,
        project_name=project.name if project else None,
        functional_area_id=part.functional_area_id,
        percentage=part.percentage,
        days=part.days,
        cost=part.cost,
        created_at=part.created_at,
        updated_at=part.updated_at,
    )
