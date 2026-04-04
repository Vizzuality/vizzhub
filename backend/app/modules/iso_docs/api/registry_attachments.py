"""Registry attachment endpoints — upload/delete."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Form, HTTPException, UploadFile

from app.core.api.deps import DBSession
from app.modules.iso_docs.api.deps import IsoDocsEditor
from app.modules.iso_docs.models.registry_attachment import RegistryAttachmentDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.schemas.registry import AttachmentResponse
from app.modules.iso_docs.services.registry_attachment_service import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE,
    delete_attachment,
    get_attachment_url,
    upload_attachment,
)

from sqlalchemy import select

logger = structlog.get_logger()

router = APIRouter()


@router.post(
    "/registries/{node_id}/rows/{row_id}/attachments",
    status_code=201,
    responses={
        404: {"description": "Row not found"},
        400: {"description": "File type not allowed or file exceeds size limit"},
    },
)
async def upload_row_attachment(
    node_id: UUID,
    row_id: UUID,
    file: UploadFile,
    db: DBSession,
    user: IsoDocsEditor,
    field_key: Annotated[str | None, Form()] = None,
) -> AttachmentResponse:
    result = await db.execute(
        select(RegistryRowDB).where(
            RegistryRowDB.id == row_id, RegistryRowDB.node_id == node_id
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="File type not allowed")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 10MB limit")

    s3_key = upload_attachment(file_bytes, file.filename or "file", file.content_type)

    attachment = RegistryAttachmentDB(
        row_id=row_id,
        node_id=node_id,
        field_key=field_key,
        filename=file.filename or "file",
        s3_key=s3_key,
        content_type=file.content_type,
        size_bytes=len(file_bytes),
        uploaded_by_id=UUID(user.user_id),
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)
    logger.info(
        "registry_attachment_uploaded",
        row_id=str(row_id),
        attachment_id=str(attachment.id),
        filename=file.filename,
    )
    resp = AttachmentResponse.model_validate(attachment)
    resp.url = get_attachment_url(attachment.s3_key)
    return resp


@router.delete(
    "/registries/attachments/{attachment_id}",
    responses={404: {"description": "Attachment not found"}},
)
async def delete_row_attachment(
    attachment_id: UUID, db: DBSession, user: IsoDocsEditor
) -> dict:
    result = await db.execute(
        select(RegistryAttachmentDB).where(RegistryAttachmentDB.id == attachment_id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    delete_attachment(attachment.s3_key)
    await db.delete(attachment)
    await db.flush()
    logger.info(
        "registry_attachment_deleted",
        attachment_id=str(attachment_id),
    )
    return {"ok": True}
