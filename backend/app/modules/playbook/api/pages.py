"""Playbook page content and version endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.content_version_service import ContentVersionService
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB
from app.modules.playbook.schemas.page import (
    PageContentResponse,
    PageSave,
    PageSaveResponse,
    VersionDetailResponse,
    VersionListItem,
)

router = APIRouter()

_versions = ContentVersionService(
    model_class=PlaybookPageVersionDB,
    entity_fk_field="node_id",
)


async def _get_page_node(db: DBSession, node_id: UUID) -> PlaybookNodeDB:
    result = await db.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.id == node_id)
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Page not found")
    if node.type != "page":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node is a group, not a page",
        )
    return node


@router.get("/{node_id}")
async def get_page(
    node_id: UUID, db: DBSession, user: CurrentUser
) -> PageContentResponse:
    node = await _get_page_node(db, node_id)
    latest = await _versions.get_latest(db, entity_id=node_id)

    return PageContentResponse(
        node_id=node.id,
        title=node.title,
        content=latest.content if latest else "",
        version=latest.version if latest else 0,
        is_public=node.is_public,
        created_by_id=latest.created_by_id if latest else None,
        created_at=latest.created_at if latest else node.created_at,
    )


@router.put("/{node_id}")
async def save_page(
    node_id: UUID, data: PageSave, db: DBSession, user: CurrentUser
) -> PageSaveResponse:
    await _get_page_node(db, node_id)

    user_id = UUID(user.user_id)
    new_version, conflict = await _versions.save_version(
        db,
        entity_id=node_id,
        content=data.content,
        user_id=user_id,
        expected_version=data.expected_version,
    )

    return PageSaveResponse(
        node_id=node_id,
        version=new_version,
        conflict=conflict,
    )


@router.get("/{node_id}/versions")
async def list_versions(
    node_id: UUID, db: DBSession, user: CurrentUser
) -> list[VersionListItem]:
    await _get_page_node(db, node_id)
    versions = await _versions.list_versions(db, entity_id=node_id)
    return [VersionListItem.model_validate(v) for v in versions]


@router.get("/{node_id}/versions/{version}")
async def get_version(
    node_id: UUID, version: int, db: DBSession, user: CurrentUser
) -> VersionDetailResponse:
    await _get_page_node(db, node_id)
    record = await _versions.get_version(db, entity_id=node_id, version=version)
    if not record:
        raise HTTPException(status_code=404, detail="Version not found")
    return VersionDetailResponse(
        node_id=node_id,
        content=record.content,
        version=record.version,
        created_by_id=record.created_by_id,
        created_at=record.created_at,
    )
