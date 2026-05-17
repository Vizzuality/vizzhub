"""Shared enrichment helpers for tracker API responses."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.schemas.report import ReportResponse
from app.modules.tracker.schemas.report_part import ReportPartResponse


def _build_report_response(
    report: ReportDB,
    user: UserDB | None,
) -> ReportResponse:
    """Map a ReportDB + optional user to a ReportResponse."""
    return ReportResponse(
        id=report.id,
        user_id=report.user_id,
        reporting_period_id=report.reporting_period_id,
        estimated=report.estimated,
        mood=report.mood,
        feedback_text=report.feedback_text,
        user_name=user.name if user else None,
        user_email=user.email if user else None,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def _build_part_response(
    part: ReportPartDB,
    project: ProjectDB | None,
) -> ReportPartResponse:
    """Map a ReportPartDB + optional project to a ReportPartResponse."""
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


async def enrich_report(report: ReportDB, db: AsyncSession) -> ReportResponse:
    """Add user_name and user_email to a report response."""
    result = await db.execute(select(UserDB).where(UserDB.id == report.user_id))
    return _build_report_response(report, result.scalar_one_or_none())


async def enrich_reports_batch(
    reports: list[ReportDB],
    db: AsyncSession,
) -> list[ReportResponse]:
    """Enrich multiple reports with a single user query."""
    if not reports:
        return []
    user_ids = {r.user_id for r in reports}
    result = await db.execute(select(UserDB).where(UserDB.id.in_(user_ids)))
    user_map: dict[UUID, UserDB] = {u.id: u for u in result.scalars().all()}
    return [_build_report_response(r, user_map.get(r.user_id)) for r in reports]


async def enrich_part(part: ReportPartDB, db: AsyncSession) -> ReportPartResponse:
    """Add project_name to a report part response."""
    result = await db.execute(select(ProjectDB).where(ProjectDB.id == part.project_id))
    return _build_part_response(part, result.scalar_one_or_none())


async def enrich_parts_batch(
    parts: list[ReportPartDB],
    db: AsyncSession,
) -> list[ReportPartResponse]:
    """Enrich multiple report parts with a single project query."""
    if not parts:
        return []
    project_ids = {p.project_id for p in parts}
    result = await db.execute(select(ProjectDB).where(ProjectDB.id.in_(project_ids)))
    project_map: dict[UUID, ProjectDB] = {p.id: p for p in result.scalars().all()}
    return [_build_part_response(p, project_map.get(p.project_id)) for p in parts]
