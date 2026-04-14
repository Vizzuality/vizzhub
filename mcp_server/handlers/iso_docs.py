"""ISO docs command handler — dispatches 8 write actions to backend services."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.core.services.content_version_service import ContentVersionService
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.iso_docs.services.registry_service import (
    get_next_row_index,
    strip_computed_keys,
    validate_row_data,
)
from app.modules.iso_docs.services import tree_service

from mcp_server.handlers._shared import (
    delete_leaf_node,
    extract_h1,
    resolve_node_by_slug,
    update_node_tree,
)

logger = structlog.get_logger()

_versions = ContentVersionService(
    model_class=IsoDocVersionDB,
    entity_fk_field="node_id",
)


async def _get_user_display_name(session: AsyncSession, user_id: UUID) -> str:
    """Resolve user display name: first+last > name > email prefix."""
    result = await session.execute(
        select(UserDB).where(UserDB.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        return str(user_id)
    if user.first_name or user.last_name:
        return " ".join(filter(None, [user.first_name, user.last_name]))
    if user.name:
        return user.name
    return user.email.split("@")[0] if user.email else str(user_id)


async def _fill_changelog_authors(
    session: AsyncSession, changelog: list, user_id: UUID,
) -> None:
    """Set author on changelog entries that are missing or 'system'."""
    display_name = await _get_user_display_name(session, user_id)
    for entry in changelog:
        if not isinstance(entry, dict):
            continue
        author = entry.get("author", "")
        if not author or author == "system":
            entry["author"] = display_name


async def _resolve_registry(
    session: AsyncSession, slug: str,
) -> tuple[IsoDocNodeDB, RegistryTypeDB]:
    """Find a registry node by slug and load its registry type."""
    node = await resolve_node_by_slug(session, IsoDocNodeDB, slug)
    if node.type not in ("registry", "widget"):
        raise ValueError(
            f"Node '{slug}' is type '{node.type}', expected 'registry' or 'widget'"
        )
    if node.registry_type_id is None:
        raise ValueError(f"Node '{slug}' has no registry type")
    result = await session.execute(
        select(RegistryTypeDB).where(RegistryTypeDB.id == node.registry_type_id)
    )
    rt = result.scalar_one_or_none()
    if rt is None:
        raise ValueError(f"Registry type not found for node '{slug}'")
    return node, rt


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


async def _create_page(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (parent_slug) is required for create_page")

    parent = await resolve_node_by_slug(
        session, IsoDocNodeDB, target, expected_type="group",
    )
    title = payload.get("title")
    if not title:
        raise ValueError("payload.title is required")

    if not await tree_service.validate_depth(session, parent.id):
        raise ValueError("Maximum tree depth exceeded")

    slug = tree_service.generate_slug(title)
    slug = await tree_service.ensure_unique_slug(session, slug)
    position = await tree_service.get_next_position(session, parent.id)

    node = IsoDocNodeDB(
        title=title,
        slug=slug,
        type="page",
        parent_id=parent.id,
        position=position,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    session.add(node)
    await session.flush()
    await session.refresh(node)

    session.add(IsoDocMetadataDB(node_id=node.id))
    await session.flush()

    logger.info(
        "mcp_iso_page_created",
        node_id=str(node.id),
        slug=slug,
        title=title,
    )
    return {"node_id": str(node.id), "slug": slug, "title": title}


async def _update_page_content(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (slug) is required for update_page_content")

    node = await resolve_node_by_slug(
        session, IsoDocNodeDB, target, expected_type="page",
    )
    content = payload.get("content")
    if content is None:
        raise ValueError("payload.content is required")

    expected_version = payload.get("expected_version")
    new_version, conflict = await _versions.save_version(
        session,
        entity_id=node.id,
        content=content,
        user_id=user_id,
        expected_version=expected_version,
    )

    h1_title = extract_h1(content)
    if h1_title and h1_title != node.title:
        node.title = h1_title
        node.slug = await tree_service.ensure_unique_slug(
            session, tree_service.generate_slug(h1_title), exclude_id=node.id,
        )
        node.updated_by_id = user_id
        await session.flush()

    logger.info(
        "mcp_iso_content_updated",
        node_id=str(node.id),
        version=new_version,
        conflict=conflict,
    )
    return {
        "node_id": str(node.id),
        "version": new_version,
        "conflict": conflict,
    }


async def _patch_page_content(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (slug) is required for patch_page_content")

    node = await resolve_node_by_slug(
        session, IsoDocNodeDB, target, expected_type="page",
    )

    operations = payload.get("operations")
    if not operations:
        raise ValueError("payload.operations is required and must not be empty")

    latest = await _versions.get_latest(session, node.id)
    if not latest:
        raise ValueError(f"Page '{target}' has no content to patch")
    content = latest.content

    for i, op in enumerate(operations):
        search = op["search"]
        replace = op["replace"]
        count = content.count(search)
        if count == 0:
            desc = op.get("description", f"operation {i + 1}")
            raise ValueError(
                f"Patch failed ({desc}): search text not found in document"
            )
        if count > 1:
            desc = op.get("description", f"operation {i + 1}")
            raise ValueError(
                f"Patch failed ({desc}): search text found {count} times, "
                f"expected exactly 1. Add surrounding context to disambiguate."
            )
        content = content.replace(search, replace, 1)

    expected_version = payload.get("expected_version")
    new_version, conflict = await _versions.save_version(
        session,
        entity_id=node.id,
        content=content,
        user_id=user_id,
        expected_version=expected_version,
    )

    h1_title = extract_h1(content)
    if h1_title and h1_title != node.title:
        node.title = h1_title
        node.slug = await tree_service.ensure_unique_slug(
            session, tree_service.generate_slug(h1_title), exclude_id=node.id,
        )
        node.updated_by_id = user_id
        await session.flush()

    logger.info(
        "mcp_iso_content_patched",
        node_id=str(node.id),
        version=new_version,
        conflict=conflict,
        operations=len(operations),
    )
    return {
        "node_id": str(node.id),
        "version": new_version,
        "conflict": conflict,
        "operations_applied": len(operations),
    }


async def _update_metadata(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (slug) is required for update_metadata")

    node = await resolve_node_by_slug(session, IsoDocNodeDB, target)

    result = await session.execute(
        select(IsoDocMetadataDB).where(IsoDocMetadataDB.node_id == node.id)
    )
    meta = result.scalar_one_or_none()

    allowed_fields = {
        "code", "standard", "clauses", "classification", "status",
        "document_date", "original_filename", "guidance", "changelog",
    }
    update = {k: v for k, v in payload.items() if k in allowed_fields}

    if "changelog" in update and update["changelog"]:
        await _fill_changelog_authors(session, update["changelog"], user_id)

    if meta:
        for field, value in update.items():
            setattr(meta, field, value)
    else:
        meta = IsoDocMetadataDB(node_id=node.id, **update)
        session.add(meta)

    await session.flush()
    await session.refresh(meta)

    logger.info(
        "mcp_iso_metadata_updated",
        node_id=str(node.id),
        fields=list(update.keys()),
    )
    return {
        "node_id": str(node.id),
        "code": meta.code,
        "status": meta.status,
        "classification": meta.classification,
        "standard": meta.standard,
        "clauses": meta.clauses,
        "guidance": meta.guidance,
        "changelog": meta.changelog,
    }


async def _update_node(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (slug) is required for update_node")

    result = await update_node_tree(
        session, IsoDocNodeDB, target, payload, user_id,
        tree_service=tree_service,
    )
    logger.info(
        "mcp_iso_node_updated",
        node_id=result["node_id"],
        slug=result["slug"],
    )
    return result


async def _delete_node(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (slug) is required for delete_node")

    await delete_leaf_node(session, IsoDocNodeDB, target)
    logger.info("mcp_iso_node_deleted", slug=target)
    return {"ok": True}


async def _create_registry_row(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (registry slug) is required for create_registry_row")

    node, rt = await _resolve_registry(session, target)
    year = payload.get("year")
    data = payload.get("data")
    if data is None:
        raise ValueError("payload.data is required")

    if rt.is_yearly and year is None:
        raise ValueError("Year is required for yearly registries")

    schema = rt.schema or []
    clean_data = strip_computed_keys(schema, data) if schema else data
    if schema:
        errors = validate_row_data(schema, clean_data)
        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")

    row_index = await get_next_row_index(session, node.id, year)
    row = RegistryRowDB(
        node_id=node.id,
        year=year,
        row_index=row_index,
        data=clean_data,
        created_by_id=user_id,
        updated_by_id=user_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)

    logger.info(
        "mcp_iso_registry_row_created",
        node_id=str(node.id),
        row_id=str(row.id),
    )
    return {
        "row_id": str(row.id),
        "data": row.data,
        "year": row.year,
    }


async def _update_registry_row(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError("target (registry slug) is required for update_registry_row")

    node, rt = await _resolve_registry(session, target)

    row_id_str = payload.get("row_id")
    if not row_id_str:
        raise ValueError("payload.row_id is required")
    row_id = UUID(row_id_str)

    update_data = payload.get("data")
    if update_data is None:
        raise ValueError("payload.data is required")

    result = await session.execute(
        select(RegistryRowDB).where(
            RegistryRowDB.id == row_id, RegistryRowDB.node_id == node.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"Row {row_id} not found in registry '{target}'")

    schema = rt.schema or []
    clean_update = strip_computed_keys(schema, update_data) if schema else update_data
    merged = {**row.data, **clean_update}
    if schema:
        errors = validate_row_data(schema, merged)
        if errors:
            raise ValueError(f"Validation errors: {'; '.join(errors)}")

    row.data = merged
    row.updated_by_id = user_id
    await session.flush()
    await session.refresh(row)

    logger.info(
        "mcp_iso_registry_row_updated",
        node_id=str(node.id),
        row_id=str(row.id),
    )
    return {"row_id": str(row.id), "data": row.data}


async def _delete_registry_row(
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    if not target:
        raise ValueError(
            "target (registry slug) is required for delete_registry_row"
        )

    node, _ = await _resolve_registry(session, target)

    row_id_str = payload.get("row_id")
    if not row_id_str:
        raise ValueError("payload.row_id is required")
    row_id = UUID(row_id_str)

    result = await session.execute(
        select(RegistryRowDB).where(
            RegistryRowDB.id == row_id, RegistryRowDB.node_id == node.id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"Row {row_id} not found in registry '{target}'")

    await session.delete(row)
    await session.flush()

    logger.info(
        "mcp_iso_registry_row_deleted",
        node_id=str(node.id),
        row_id=str(row_id),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Action dispatch
# ---------------------------------------------------------------------------

_ACTIONS: dict[str, object] = {
    "create_page": _create_page,
    "update_page_content": _update_page_content,
    "patch_page_content": _patch_page_content,
    "update_metadata": _update_metadata,
    "update_node": _update_node,
    "delete_node": _delete_node,
    "create_registry_row": _create_registry_row,
    "update_registry_row": _update_registry_row,
    "delete_registry_row": _delete_registry_row,
}


async def execute(
    action: str,
    target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    """Dispatch an ISO docs write action to the appropriate handler."""
    handler = _ACTIONS.get(action)
    if handler is None:
        raise ValueError(f"Unknown ISO docs action: '{action}'")
    return await handler(target, payload, user_id, session)
