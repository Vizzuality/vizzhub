"""Public interface for the tracker module.

Other modules should import from here, never from tracker internals.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.progress_report import ProgressReportDB


async def has_tracker_references(
    project_id: UUID, db: AsyncSession
) -> list[str]:
    """Check if a project has tracker references that block deletion.

    Returns a list of human-readable reference descriptions.
    """
    from sqlalchemy import text

    table_check = await db.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' "
            "AND tablename IN ('report_parts', 'progress_reports')"
        )
    )
    existing_tables = {row[0] for row in table_check.fetchall()}

    references: list[str] = []

    if "report_parts" in existing_tables:
        rp_count = (
            await db.execute(
                select(func.count())
                .select_from(ReportPartDB)
                .where(ReportPartDB.project_id == project_id)
            )
        ).scalar() or 0
        if rp_count > 0:
            references.append(
                f"Cannot delete: project has {rp_count} time report entries."
            )

    if "progress_reports" in existing_tables:
        pr_count = (
            await db.execute(
                select(func.count())
                .select_from(ProgressReportDB)
                .where(ProgressReportDB.project_id == project_id)
            )
        ).scalar() or 0
        if pr_count > 0:
            references.append(
                f"Cannot delete: project has {pr_count} progress reports."
            )

    return references
