"""Admin asset management API — centralized view of all uploaded files."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.config import get_settings
from app.core.api.deps import AdminUser, DBSession
from app.core.services.s3 import get_s3_client
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_attachment import RegistryAttachmentDB
from app.modules.iso_docs.services.registry_attachment_service import (
    delete_attachment,
    get_attachment_url,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/admin/assets", tags=["admin-assets"])


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    s3_key: str
    url: str | None = None
    content_type: str
    size_bytes: int
    uploaded_by_id: UUID | None
    created_at: datetime
    node_id: UUID | None
    node_title: str | None = None
    row_id: UUID
    field_key: str | None


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
    page: int
    page_size: int


@router.get("")
async def list_assets(
    db: DBSession,
    _user: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    content_type: Annotated[str | None, Query()] = None,
) -> AssetListResponse:
    base = select(
        RegistryAttachmentDB,
        IsoDocNodeDB.title.label("node_title"),
    ).outerjoin(IsoDocNodeDB, RegistryAttachmentDB.node_id == IsoDocNodeDB.id)

    if content_type:
        base = base.where(RegistryAttachmentDB.content_type.ilike(f"%{content_type}%"))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    rows = (
        await db.execute(
            base.order_by(RegistryAttachmentDB.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items: list[AssetResponse] = []
    for attachment, node_title in rows:
        resp = AssetResponse.model_validate(attachment)
        resp.url = get_attachment_url(attachment.s3_key)
        resp.node_title = node_title
        items.append(resp)

    return AssetListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# S3 image management (Playbook / ISO Docs images)
# ---------------------------------------------------------------------------

S3_PREFIXES: dict[str, str] = {
    "playbook": "playbook/images/",
    "iso-docs": "iso-docs/images/",
}


class S3ImageItem(BaseModel):
    key: str
    filename: str
    url: str
    size_bytes: int
    last_modified: datetime


class S3ImageListResponse(BaseModel):
    items: list[S3ImageItem]
    total: int
    prefix: str


def _image_url(key: str) -> str:
    settings = get_settings()
    if settings.playbook_public_url:
        # Playbook origin has /playbook as origin path, so strip the prefix.
        # ISO docs origin maps directly to bucket root, so keep the full key.
        cf_path = key.removeprefix("playbook/") if key.startswith("playbook/") else key
        return f"{settings.playbook_public_url}/{cf_path}"
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.assets_bucket_name, "Key": key},
        ExpiresIn=7 * 24 * 3600,
    )


@router.get("/images")
async def list_images(
    _user: AdminUser,
    source: Annotated[Literal["playbook", "iso-docs"], Query()],
) -> S3ImageListResponse:
    prefix = S3_PREFIXES[source]
    settings = get_settings()
    client = get_s3_client()

    objects: list[S3ImageItem] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=settings.assets_bucket_name, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.removeprefix(prefix)
            if not filename:
                continue
            objects.append(
                S3ImageItem(
                    key=key,
                    filename=filename,
                    url=_image_url(key),
                    size_bytes=obj["Size"],
                    last_modified=obj["LastModified"].replace(tzinfo=UTC),
                )
            )

    objects.sort(key=lambda o: o.last_modified, reverse=True)

    return S3ImageListResponse(
        items=objects,
        total=len(objects),
        prefix=prefix,
    )


def _has_valid_prefix(key: str) -> bool:
    return any(key.startswith(p) for p in S3_PREFIXES.values())


@router.delete(
    "/images",
    responses={400: {"description": "Invalid S3 key prefix"}},
)
async def delete_image(
    key: Annotated[str, Query()],
    _user: AdminUser,
) -> dict:
    if not _has_valid_prefix(key):
        raise HTTPException(status_code=400, detail="Invalid S3 key prefix")

    settings = get_settings()
    get_s3_client().delete_object(Bucket=settings.assets_bucket_name, Key=key)
    logger.info("admin_image_deleted", s3_key=key)
    return {"ok": True}


class BatchDeleteImagesRequest(BaseModel):
    keys: list[str]


@router.post("/images/batch-delete")
async def batch_delete_images(body: BatchDeleteImagesRequest, _user: AdminUser) -> dict:
    settings = get_settings()
    client = get_s3_client()
    valid_keys = [k for k in body.keys if _has_valid_prefix(k)]
    for key in valid_keys:
        client.delete_object(Bucket=settings.assets_bucket_name, Key=key)
    deleted = len(valid_keys)
    logger.info("admin_images_batch_deleted", count=deleted)
    return {"ok": True, "deleted": deleted}


# ---------------------------------------------------------------------------
# Registry attachment management (DB-tracked)
# ---------------------------------------------------------------------------


@router.delete(
    "/{asset_id}",
    responses={404: {"description": "Asset not found"}},
)
async def delete_asset(asset_id: UUID, db: DBSession, _user: AdminUser) -> dict:
    result = await db.execute(
        select(RegistryAttachmentDB).where(RegistryAttachmentDB.id == asset_id)
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(status_code=404, detail="Asset not found")

    delete_attachment(attachment.s3_key)
    await db.delete(attachment)
    await db.flush()
    logger.info(
        "admin_asset_deleted",
        asset_id=str(asset_id),
        filename=attachment.filename,
    )
    return {"ok": True}
