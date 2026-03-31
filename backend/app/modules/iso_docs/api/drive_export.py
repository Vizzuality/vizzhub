"""ISO Docs Google Drive export endpoint."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, func as sa_func

from app.core.api.deps import DBSession, limiter
from app.core.models.job import Job, JobStatus, JobType
from app.core.services.integration_token_service import IntegrationTokenService
from app.core.services.job_service import JobService
from app.modules.iso_docs.api.deps import IsoDocsEditor
from app.modules.iso_docs.models.drive_mapping import IsoDocDriveMappingDB
from app.modules.iso_docs.schemas.drive_export import (
    DriveFolderRequest,
    DriveExportResponse,
    DriveStatusResponse,
)
from app.modules.iso_docs.services.google_drive_oauth import GoogleDriveOAuth, PROVIDER
from app.modules.iso_docs.services.drive_export_service import ROOT_FOLDER_KEY
from app.utils.redis import get_redis_pool

logger = structlog.get_logger()

router = APIRouter()


@router.get("/drive/status")
@limiter.limit("30/minute")
async def get_drive_export_status(
    request: Request, user: IsoDocsEditor, db: DBSession
) -> DriveStatusResponse:
    status = await GoogleDriveOAuth.get_status(db)
    if not status["connected"]:
        return DriveStatusResponse(connected=False)

    root_folder_id = await IntegrationTokenService.get_setting(
        db, PROVIDER, ROOT_FOLDER_KEY
    )

    count_result = await db.execute(
        select(sa_func.count()).select_from(IsoDocDriveMappingDB)
    )
    doc_count = count_result.scalar_one()

    last_export_result = await db.execute(
        select(sa_func.max(IsoDocDriveMappingDB.last_exported_at))
    )
    last_export = last_export_result.scalar_one()

    return DriveStatusResponse(
        connected=True,
        last_export_at=last_export,
        root_folder_id=root_folder_id,
        exported_doc_count=doc_count,
    )


@router.put("/drive/folder")
@limiter.limit("10/minute")
async def save_drive_folder(
    request: Request, user: IsoDocsEditor, db: DBSession, body: DriveFolderRequest
) -> dict:
    await IntegrationTokenService.set_setting(
        db, PROVIDER, ROOT_FOLDER_KEY, body.folder_id.strip()
    )
    logger.info("drive_root_folder_saved", folder_id=body.folder_id)
    return {"status": "success", "folder_id": body.folder_id.strip()}


@router.post("/drive/export")
@limiter.limit("5/minute")
async def trigger_drive_export(
    request: Request, user: IsoDocsEditor, db: DBSession
) -> DriveExportResponse:
    running = await db.execute(
        select(Job).where(
            Job.type == JobType.EXPORT_GDRIVE,
            Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
        )
    )
    if running.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Export already in progress")

    token = await GoogleDriveOAuth.get_valid_token(db)
    if not token:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    folder_id = await IntegrationTokenService.get_setting(
        db, PROVIDER, ROOT_FOLDER_KEY
    )
    if not folder_id:
        raise HTTPException(
            status_code=400, detail="Root folder not configured"
        )

    job = await JobService.create_job(
        db,
        job_type=JobType.EXPORT_GDRIVE,
        name="Export ISO Docs to Google Drive",
        params={},
        created_by=user.email,
    )

    pool = await get_redis_pool()
    arq_job = await pool.enqueue_job(
        "export_iso_docs_gdrive_task", str(job.id)
    )
    await pool.aclose()

    if arq_job:
        await JobService.set_arq_job_id(db, job.id, arq_job.job_id)

    logger.info("drive_export_triggered", job_id=str(job.id))
    return DriveExportResponse(job_id=job.id)
