"""Admin asset management API — centralized view of all uploaded files."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.core.api.deps import AdminUser, DBSession
from app.modules.iso_docs.models.registry_attachment import RegistryAttachmentDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
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
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    content_type: str | None = Query(None),
) -> AssetListResponse:
    base = select(
        RegistryAttachmentDB,
        IsoDocNodeDB.title.label("node_title"),
    ).outerjoin(
        IsoDocNodeDB, RegistryAttachmentDB.node_id == IsoDocNodeDB.id
    )

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


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: UUID, db: DBSession, _user: AdminUser
) -> dict:
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
