"""ARQ task for exporting ISO Docs to Google Drive."""

import structlog

from app.modules.iso_docs.services.drive_export_service import DriveExportService

logger = structlog.get_logger()

JOB_NAME = "export_iso_docs_gdrive_task"


async def export_iso_docs_gdrive_task(ctx: dict, job_id: str) -> dict:
    logger.info("job_started", job_name=JOB_NAME, job_id=job_id)
    db = ctx["db"]
    try:
        svc = DriveExportService()
        result = await svc.export_tree(db, job_id)
    except Exception:
        logger.exception("job_failed", job_name=JOB_NAME, job_id=job_id)
        raise
    logger.info(
        "job_completed",
        job_name=JOB_NAME,
        job_id=job_id,
        exported=result.get("exported") if isinstance(result, dict) else None,
    )
    return result
