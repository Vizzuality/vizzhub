"""ISO Docs asset upload endpoint — images for page content."""

import structlog
from fastapi import APIRouter, HTTPException, UploadFile, status

from app.modules.iso_docs.api.deps import IsoDocsEditor
from app.modules.iso_docs.services.asset_service import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE,
    is_upload_available,
    upload_image,
)

logger = structlog.get_logger()

router = APIRouter()


@router.get("/status")
async def asset_status(_user: IsoDocsEditor) -> dict:
    return {"available": is_upload_available()}


@router.post("/upload")
async def upload_asset(file: UploadFile, user: IsoDocsEditor) -> dict:
    if not is_upload_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image uploads are not configured",
        )

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Accepted: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    url = upload_image(file_bytes, file.filename or "image", file.content_type)
    logger.info(
        "iso_docs_image_uploaded",
        filename=file.filename,
        user_id=user.user_id,
    )
    return {"url": url}
