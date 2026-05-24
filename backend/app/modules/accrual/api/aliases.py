"""HTTP endpoints for accrual aliases.

Mounted under ``/api/accrual/aliases``. Writes require ``ACCRUAL_MANAGE``; reads
require ``ACCRUAL_VIEW``.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.modules.accrual.models.accrual_alias import AccrualAliasDB
from app.modules.accrual.schemas.accrual_alias import (
    AccrualAlias,
    AccrualAliasBulkCreate,
    AccrualAliasCreate,
    AccrualAliasUpdate,
)
from app.modules.accrual.services import alias_service

logger = structlog.get_logger()
router = APIRouter()

AccrualViewer = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_VIEW))]
AccrualManager = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_MANAGE))]


def _parse_user_id(token: TokenData) -> UUID | None:
    return UUID(token.user_id) if token.user_id else None


def _serialize(
    alias: AccrualAliasDB,
    project_name: str | None = None,
    project_code: str | None = None,
) -> AccrualAlias:
    return AccrualAlias(
        id=alias.id,
        excel_code=alias.excel_code,
        project_id=alias.project_id,
        project_name=project_name,
        project_code=project_code,
        weight=alias.weight,
        notes=alias.notes,
        created_by=alias.created_by,
        created_at=alias.created_at,
    )


@router.get(
    "",
    response_model=list[AccrualAlias],
    responses={403: {"description": "Insufficient permissions"}},
)
async def list_aliases(
    _user: AccrualViewer,
    db: DBSession,
    excel_code: Annotated[str | None, Query()] = None,
    project_id: Annotated[UUID | None, Query()] = None,
) -> list[AccrualAlias]:
    """List aliases. Order: by excel_code, then created_at."""
    rows = await alias_service.list_aliases(db, excel_code=excel_code, project_id=project_id)
    return [
        _serialize(alias, project_name=project.name, project_code=project.code)
        for alias, project in rows
    ]


@router.post(
    "",
    response_model=AccrualAlias,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Project not found"},
        409: {"description": "Alias already exists for this (excel_code, project_id)"},
    },
)
async def create_alias(
    payload: AccrualAliasCreate,
    user: AccrualManager,
    db: DBSession,
) -> AccrualAlias:
    try:
        alias = await alias_service.create_alias(
            db,
            excel_code=payload.excel_code,
            project_id=payload.project_id,
            weight=payload.weight,
            notes=payload.notes,
            created_by=_parse_user_id(user),
        )
    except alias_service.ProjectNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except alias_service.AliasConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize(alias)


@router.post(
    "/bulk",
    response_model=list[AccrualAlias],
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "One of the referenced projects not found"},
        409: {"description": "Conflicting alias for excel_code"},
    },
)
async def bulk_create_aliases(
    payload: AccrualAliasBulkCreate,
    user: AccrualManager,
    db: DBSession,
) -> list[AccrualAlias]:
    """Map one Excel code to N tracker projects in a single SAVEPOINT.

    With ``replace_existing=true`` any prior aliases for this code are deleted
    first — idempotent for the "Map this row to these projects" UI flow.
    """
    try:
        created = await alias_service.bulk_create_aliases(
            db,
            excel_code=payload.excel_code,
            mappings=[(m.project_id, m.weight, m.notes) for m in payload.mappings],
            created_by=_parse_user_id(user),
            replace_existing=payload.replace_existing,
        )
    except alias_service.ProjectNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except alias_service.AliasConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return [_serialize(alias) for alias in created]


@router.patch(
    "/{alias_id}",
    response_model=AccrualAlias,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Alias not found"},
    },
)
async def update_alias(
    alias_id: UUID,
    payload: AccrualAliasUpdate,
    _user: AccrualManager,
    db: DBSession,
) -> AccrualAlias:
    try:
        alias = await alias_service.update_alias(
            db,
            alias_id=alias_id,
            weight=payload.weight,
            notes=payload.notes,
        )
    except alias_service.AliasNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize(alias)


@router.delete(
    "/{alias_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Alias not found"},
    },
)
async def delete_alias(
    alias_id: UUID,
    _user: AccrualManager,
    db: DBSession,
) -> None:
    try:
        await alias_service.delete_alias(db, alias_id=alias_id)
    except alias_service.AliasNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
