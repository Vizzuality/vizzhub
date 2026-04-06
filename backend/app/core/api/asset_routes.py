"""Factory for asset upload routers shared by doc modules."""

from __future__ import annotations

from typing import Callable

import structlog
from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.services.doc_asset_service import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_SIZE,
)

logger = structlog.get_logger()


def create_asset_router(
    *,
    is_upload_available: Callable[[], bool],
    upload_image: Callable[[bytes, str, str], str],
    log_event: str,
) -> APIRouter:
    """Build an asset upload router for a doc module.

    Args:
        is_upload_available: Check if S3 uploads are configured.
        upload_image: Module-specific upload function.
        log_event: Event name for the upload log (e.g. "playbook_image_uploaded").
    """
    router = APIRouter()

    @router.get("/status")
    async def asset_status() -> dict:
        return {"available": is_upload_available()}

    @router.post("/upload")
    async def upload_asset(file: UploadFile) -> dict:
        if not is_upload_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Image uploads are not configured",
            )

        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "File type not allowed. Accepted: "
                    f"{', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
                ),
            )

        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=(
                    "File too large. Maximum size: "
                    f"{MAX_FILE_SIZE // (1024 * 1024)} MB"
                ),
            )

        url = upload_image(
            file_bytes, file.filename or "image", file.content_type
        )
        logger.info(log_event, filename=file.filename)
        return {"url": url}

    return router
