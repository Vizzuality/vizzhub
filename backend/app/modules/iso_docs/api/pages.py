"""ISO Docs page content and version endpoints."""

from __future__ import annotations

from collections import Counter
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from typing import Annotated

from app.core.api.deps import CurrentUser, DBSession
from app.core.models.user import UserDB
from app.core.services.content_version_service import ContentVersionService
from app.modules.iso_docs.api.deps import IsoDocsEditor, is_iso_docs_editor
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.schemas.page import (
    PageContentResponse,
    PageSave,
    PageSaveResponse,
    SearchResultItem,
    VersionDetailResponse,
    VersionListItem,
)
from app.modules.iso_docs.services.tree_service import ensure_unique_slug, generate_slug

logger = structlog.get_logger()

router = APIRouter()

_versions = ContentVersionService(
    model_class=IsoDocVersionDB,
    entity_fk_field="node_id",
)


async def _check_confidential(db: DBSession, node_id: UUID, user: CurrentUser) -> None:
    """Raise 403 if node is confidential and user is not an editor."""
    if is_iso_docs_editor(user):
        return
    meta_result = await db.execute(
        select(IsoDocMetadataDB.classification).where(
            IsoDocMetadataDB.node_id == node_id
        )
    )
    classification = meta_result.scalar_one_or_none()
    if classification == "confidential":
        raise HTTPException(status_code=403, detail="Access denied")


async def _get_page_node(db: DBSession, node_id: UUID) -> IsoDocNodeDB:
    result = await db.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.id == node_id)
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


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_snippet(content: str, query: str, max_len: int = 150) -> str:
    """Extract a text snippet around the first match, stripping markdown."""
    lower = content.lower()
    pos = lower.find(query.lower())
    if pos == -1:
        plain = content[:max_len]
    else:
        start = max(0, pos - 60)
        end = min(len(content), pos + len(query) + 90)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""
        plain = prefix + content[start:end] + suffix
    plain = plain.replace("#", "").replace("*", "").replace("|", " ").replace("\n", " ")
    return " ".join(plain.split())[:max_len]


@router.get("/search")
async def search_pages(
    db: DBSession,
    user: CurrentUser,
    q: Annotated[str, Query(min_length=2, max_length=200)] = "",
) -> list[SearchResultItem]:
    q = q.strip()
    if len(q) < 2:
        return []

    safe = _escape_like(q)

    latest = (
        select(
            IsoDocVersionDB.node_id,
            IsoDocVersionDB.content,
        )
        .distinct(IsoDocVersionDB.node_id)
        .order_by(IsoDocVersionDB.node_id, IsoDocVersionDB.version.desc())
    ).subquery()

    query = (
        select(
            IsoDocNodeDB.id.label("node_id"),
            IsoDocNodeDB.title,
            latest.c.content,
            IsoDocMetadataDB.code,
        )
        .join(latest, latest.c.node_id == IsoDocNodeDB.id)
        .outerjoin(IsoDocMetadataDB, IsoDocMetadataDB.node_id == IsoDocNodeDB.id)
        .where(
            (IsoDocNodeDB.title.ilike(f"%{safe}%"))
            | (latest.c.content.ilike(f"%{safe}%"))
        )
        .order_by(IsoDocNodeDB.title)
    )

    if not is_iso_docs_editor(user):
        query = query.where(
            (IsoDocMetadataDB.classification == None)  # noqa: E711
            | (IsoDocMetadataDB.classification != "confidential")
        )

    result = await db.execute(query)
    rows = result.all()

    logger.info("iso_doc_search", query=q, result_count=len(rows))

    return [
        SearchResultItem(
            node_id=row.node_id,
            title=row.title,
            snippet=_build_snippet(row.content or "", q),
            code=row.code,
        )
        for row in rows
    ]


@router.get(
    "/{node_id}",
    responses={
        400: {"description": "Node is a group, not a page"},
        403: {"description": "Access denied for confidential document"},
        404: {"description": "Page not found"},
    },
)
async def get_page(
    node_id: UUID, db: DBSession, user: CurrentUser
) -> PageContentResponse:
    await _check_confidential(db, node_id, user)
    node = await _get_page_node(db, node_id)
    latest = await _versions.get_latest(db, entity_id=node_id)

    return PageContentResponse(
        node_id=node.id,
        title=node.title,
        content=latest.content if latest else "",
        version=latest.version if latest else 0,
        created_by_id=latest.created_by_id if latest else None,
        created_at=latest.created_at if latest else node.created_at,
    )


@router.put(
    "/{node_id}",
    responses={
        400: {"description": "Node is a group, not a page"},
        404: {"description": "Page not found"},
    },
)
async def save_page(
    node_id: UUID, data: PageSave, db: DBSession, user: IsoDocsEditor
) -> PageSaveResponse:
    node = await _get_page_node(db, node_id)

    user_id = UUID(user.user_id)
    new_version, conflict = await _versions.save_version(
        db,
        entity_id=node_id,
        content=data.content,
        user_id=user_id,
        expected_version=data.expected_version,
    )

    h1_title = _extract_h1(data.content)
    if h1_title and h1_title != node.title:
        node.title = h1_title
        node.slug = await ensure_unique_slug(
            db, generate_slug(h1_title), node.parent_id, exclude_id=node_id,
        )
        node.updated_by_id = user_id
        await db.flush()

    logger.info("iso_doc_page_saved", node_id=str(node_id), version=new_version, conflict=conflict)
    return PageSaveResponse(
        node_id=node_id,
        version=new_version,
        conflict=conflict,
    )


def _extract_h1(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped and not stripped.startswith("#"):
            break
    return None


def _compute_line_diff(old: str, new: str) -> tuple[int, int]:
    """Return (lines_added, lines_removed) between two content strings."""
    old_counts = Counter(old.splitlines())
    new_counts = Counter(new.splitlines())
    added = sum((new_counts - old_counts).values())
    removed = sum((old_counts - new_counts).values())
    return added, removed


async def _resolve_user_names(
    db: DBSession, user_ids: set[UUID],
) -> dict[UUID, str]:
    """Batch-resolve user IDs to display names."""
    if not user_ids:
        return {}
    result = await db.execute(
        select(UserDB).where(UserDB.id.in_(user_ids))
    )
    users = result.scalars().all()
    names: dict[UUID, str] = {}
    for u in users:
        if u.first_name or u.last_name:
            names[u.id] = " ".join(filter(None, [u.first_name, u.last_name]))
        elif u.name:
            names[u.id] = u.name
        else:
            names[u.id] = u.email.split("@")[0] if u.email else str(u.id)
    return names


@router.get(
    "/{node_id}/versions",
    responses={
        400: {"description": "Node is a group, not a page"},
        403: {"description": "Access denied for confidential document"},
        404: {"description": "Page not found"},
    },
)
async def list_versions(
    node_id: UUID, db: DBSession, user: CurrentUser
) -> list[VersionListItem]:
    await _check_confidential(db, node_id, user)
    await _get_page_node(db, node_id)
    versions = await _versions.list_versions(db, entity_id=node_id)

    user_ids = {v.created_by_id for v in versions if v.created_by_id}
    user_names = await _resolve_user_names(db, user_ids)

    items = []
    for i, v in enumerate(versions):
        prev_content = versions[i + 1].content if i + 1 < len(versions) else ""
        added, removed = _compute_line_diff(prev_content, v.content)
        items.append(VersionListItem(
            version=v.version,
            created_by_id=v.created_by_id,
            created_by_name=user_names.get(v.created_by_id) if v.created_by_id else None,
            created_at=v.created_at,
            lines_added=added,
            lines_removed=removed,
        ))
    return items


@router.get(
    "/{node_id}/versions/{version}",
    responses={
        403: {"description": "Access denied for confidential document"},
        404: {"description": "Version not found"},
    },
)
async def get_version(
    node_id: UUID, version: int, db: DBSession, user: CurrentUser
) -> VersionDetailResponse:
    await _check_confidential(db, node_id, user)
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
