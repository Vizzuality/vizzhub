"""Playbook asset upload endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.core.api.deps import CurrentUser
from app.modules.playbook.services.asset_service import is_upload_available

router = APIRouter()


@router.get("/status")
async def asset_status(user: CurrentUser) -> dict:
    return {"available": is_upload_available()}


@router.post("/upload")
async def upload_asset(user: CurrentUser) -> dict:
    if not is_upload_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image uploads are not yet available",
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="S3 upload not yet implemented — waiting for bucket provisioning",
    )
