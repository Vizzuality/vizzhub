"""Registry type CRUD endpoints."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.modules.iso_docs.api.deps import IsoDocsEditor
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.iso_docs.schemas.registry import (
    RegistryTypeCreate,
    RegistryTypeResponse,
    RegistryTypeUpdate,
)

logger = structlog.get_logger()

_NOT_FOUND = "Registry type not found"

router = APIRouter()


def _slugify(name: str) -> str:
    return "-".join(name.lower().split())


@router.get("/registry-types")
async def list_registry_types(
    db: DBSession, user: CurrentUser
) -> list[RegistryTypeResponse]:
    result = await db.execute(
        select(RegistryTypeDB).order_by(RegistryTypeDB.name)
    )
    return [
        RegistryTypeResponse.model_validate(rt) for rt in result.scalars()
    ]


@router.get(
    "/registry-types/{type_id}",
    responses={404: {"description": _NOT_FOUND}},
)
async def get_registry_type(
    type_id: UUID, db: DBSession, user: CurrentUser
) -> RegistryTypeResponse:
    result = await db.execute(
        select(RegistryTypeDB).where(RegistryTypeDB.id == type_id)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return RegistryTypeResponse.model_validate(rt)


@router.post("/registry-types", status_code=201)
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
    result = await db.execute(
        select(RegistryTypeDB).where(RegistryTypeDB.id == type_id)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

    update = data.model_dump(exclude_unset=True)
    if "schema_" in update:
        update["schema"] = update.pop("schema_")
    if "name" in update:
        update["slug"] = _slugify(update["name"])

    for field, value in update.items():
        setattr(rt, field, value)
    rt.updated_by_id = UUID(user.user_id)
    await db.flush()
    await db.refresh(rt)
    logger.info("registry_type_updated", type_id=str(type_id))
    return RegistryTypeResponse.model_validate(rt)


@router.delete(
    "/registry-types/{type_id}",
    responses={404: {"description": _NOT_FOUND}},
)
async def delete_registry_type(
    type_id: UUID, db: DBSession, user: IsoDocsEditor
) -> dict:
    result = await db.execute(
        select(RegistryTypeDB).where(RegistryTypeDB.id == type_id)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)

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
