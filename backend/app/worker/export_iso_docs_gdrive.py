"""ARQ task for exporting ISO Docs to Google Drive."""

import structlog

from app.modules.iso_docs.services.drive_export_service import DriveExportService

logger = structlog.get_logger()


async def export_iso_docs_gdrive_task(ctx: dict, job_id: str) -> dict:
    db = ctx["db"]
    svc = DriveExportService()
    return await svc.export_tree(db, job_id)
