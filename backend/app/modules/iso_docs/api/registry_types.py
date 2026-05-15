"""Registry type CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import CurrentUser, DBSession
from app.modules.iso_docs.api.deps import (
    IsoDocsEditor,
    get_visible_node_ids,
    is_iso_docs_editor,
)
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.iso_docs.schemas.registry import (
    ColumnVisibilityUpdate,
    RegistryTypeCreate,
    RegistryTypeResponse,
    RegistryTypeUpdate,
)

logger = structlog.get_logger()

_NOT_FOUND = "Registry type not found"

router = APIRouter()


def _slugify(name: str) -> str:
    return "-".join(name.lower().split())


async def _get_registry_type_or_404(db: DBSession, type_id: UUID) -> RegistryTypeDB:
    result = await db.execute(
        select(RegistryTypeDB).where(RegistryTypeDB.id == type_id)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return rt


def _detect_column_renames(
    old_schema: list[dict], new_schema: list[dict],
) -> dict[str, str]:
    """Detect columns whose key changed between two schemas.

    Pairs keys removed from the old schema with keys added in the new schema
    by their position among the unmatched columns, but only when both have
    the same `type` (renaming a string column should not be confused with
    deleting a string and adding a date). Returns {old_key: new_key}.
    """
    new_keys = {col["key"] for col in new_schema}
    old_keys = {col["key"] for col in old_schema}
    removed = [col for col in old_schema if col["key"] not in new_keys]
    added = [col for col in new_schema if col["key"] not in old_keys]
    renames: dict[str, str] = {}
    for old_col, new_col in zip(removed, added):
        if old_col.get("type") == new_col.get("type"):
            renames[old_col["key"]] = new_col["key"]
    return renames


async def _migrate_renamed_keys(
    db: AsyncSession, type_id: UUID, renames: dict[str, str],
) -> int:
    """Rewrite renamed keys in registry_rows.data for all rows of nodes
    using this registry type. Each rename is a single jsonb statement.
    Returns total rows touched.
    """
    if not renames:
        return 0
    affected = 0
    for old_key, new_key in renames.items():
        result = await db.execute(
            text("""
                UPDATE registry_rows
                SET data = (data - CAST(:old_key AS text))
                       || jsonb_build_object(
                              CAST(:new_key AS text),
                              data -> CAST(:old_key AS text)
                          )
                WHERE node_id IN (
                    SELECT id FROM iso_doc_nodes WHERE registry_type_id = :type_id
                )
                AND data ? CAST(:old_key AS text)
            """),
            {"old_key": old_key, "new_key": new_key, "type_id": type_id},
        )
        affected += result.rowcount or 0
    return affected


async def _visible_registry_type_ids(
    db: AsyncSession, user: CurrentUser
) -> set[UUID] | None:
    """Return the set of `registry_type_id`s referenced by nodes visible to the user.

    Editors see all types — returns None as a sentinel for "no filter".
    Non-editors see only types attached to nodes inside `policies` / `procedures`.
    """
    if is_iso_docs_editor(user):
        return None
    visible = await get_visible_node_ids(db)
    if not visible:
        return set()
    result = await db.execute(
        select(IsoDocNodeDB.registry_type_id)
        .where(
            IsoDocNodeDB.id.in_(visible),
            IsoDocNodeDB.registry_type_id.is_not(None),
        )
        .distinct()
    )
    return {row[0] for row in result if row[0] is not None}


@router.get("/registry-types")
async def list_registry_types(
    db: DBSession, user: CurrentUser
) -> list[RegistryTypeResponse]:
    """List registry types. Non-editors only see types attached to visible nodes."""
    allowed = await _visible_registry_type_ids(db, user)
    query = select(RegistryTypeDB).order_by(RegistryTypeDB.name)
    if allowed is not None:
        if not allowed:
            return []
        query = query.where(RegistryTypeDB.id.in_(allowed))
    result = await db.execute(query)
    return [
        RegistryTypeResponse.model_validate(rt) for rt in result.scalars()
    ]


@router.get(
    "/registry-types/{type_id}",
    responses={
        403: {"description": "Access denied"},
        404: {"description": _NOT_FOUND},
    },
)
async def get_registry_type(
    type_id: UUID, db: DBSession, user: CurrentUser
) -> RegistryTypeResponse:
    """Get a registry type. Non-editors only see types attached to visible nodes."""
    allowed = await _visible_registry_type_ids(db, user)
    if allowed is not None and type_id not in allowed:
        raise HTTPException(status_code=403, detail="Access denied")
    rt = await _get_registry_type_or_404(db, type_id)
    return RegistryTypeResponse.model_validate(rt)


@router.post(
    "/registry-types",
    status_code=201,
    responses={409: {"description": "Registry type with this name already exists"}},
)
async def create_registry_type(
    data: RegistryTypeCreate, db: DBSession, user: IsoDocsEditor
) -> RegistryTypeResponse:
    slug = _slugify(data.name)
    existing = await db.execute(
        select(RegistryTypeDB).where(RegistryTypeDB.slug == slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Registry type with this name already exists")

    rt = RegistryTypeDB(
        name=data.name,
        slug=slug,
        description=data.description,
        is_yearly=data.is_yearly,
        schema=[col.model_dump() for col in data.schema_],
        created_by_id=UUID(user.user_id),
        updated_by_id=UUID(user.user_id),
    )
    db.add(rt)
    await db.flush()
    await db.refresh(rt)
    logger.info("registry_type_created", type_id=str(rt.id), name=data.name)
    return RegistryTypeResponse.model_validate(rt)


@router.patch(
    "/registry-types/{type_id}",
    responses={404: {"description": _NOT_FOUND}},
)
async def update_registry_type(
    type_id: UUID, data: RegistryTypeUpdate, db: DBSession, user: IsoDocsEditor
) -> RegistryTypeResponse:
    rt = await _get_registry_type_or_404(db, type_id)
    old_schema = list(rt.schema or [])

    update = data.model_dump(exclude_unset=True)
    if "schema_" in update:
        update["schema"] = update.pop("schema_")
    if "name" in update:
        update["slug"] = _slugify(update["name"])

    for field, value in update.items():
        setattr(rt, field, value)
    rt.updated_by_id = UUID(user.user_id)

    renames = (
        _detect_column_renames(old_schema, rt.schema)
        if "schema" in update else {}
    )

    await db.flush()

    if renames:
        rows_migrated = await _migrate_renamed_keys(db, type_id, renames)
        logger.info(
            "registry_type_columns_renamed",
            type_id=str(type_id),
            renames=renames,
            rows_migrated=rows_migrated,
        )

    await db.refresh(rt)
    logger.info("registry_type_updated", type_id=str(type_id))
    return RegistryTypeResponse.model_validate(rt)


@router.patch(
    "/registry-types/{type_id}/column-visibility",
    responses={404: {"description": _NOT_FOUND}},
)
async def update_column_visibility(
    type_id: UUID,
    data: ColumnVisibilityUpdate,
    db: DBSession,
    user: IsoDocsEditor,
) -> RegistryTypeResponse:
    rt = await _get_registry_type_or_404(db, type_id)

    hidden_set = set(data.hidden_columns)
    rt.schema = [
        {**col, "hidden": True} if col["key"] in hidden_set
        else {k: v for k, v in col.items() if k != "hidden"}
        for col in rt.schema
    ]
    rt.updated_by_id = UUID(user.user_id)
    await db.flush()
    await db.refresh(rt)
    logger.info(
        "registry_type_column_visibility_updated",
        type_id=str(type_id),
        hidden_columns=data.hidden_columns,
    )
    return RegistryTypeResponse.model_validate(rt)


@router.delete(
    "/registry-types/{type_id}",
    responses={
        404: {"description": _NOT_FOUND},
        409: {"description": "Cannot delete registry type while nodes reference it"},
    },
)
async def delete_registry_type(
    type_id: UUID, db: DBSession, user: IsoDocsEditor
) -> dict:
    rt = await _get_registry_type_or_404(db, type_id)

    nodes_result = await db.execute(
        select(IsoDocNodeDB.id).where(IsoDocNodeDB.registry_type_id == type_id).limit(1)
    )
    if nodes_result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Cannot delete registry type while nodes reference it",
        )

    await db.delete(rt)
    await db.flush()
    logger.info("registry_type_deleted", type_id=str(type_id))
    return {"ok": True}
