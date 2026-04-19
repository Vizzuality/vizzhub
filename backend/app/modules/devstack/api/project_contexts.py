"""REST API for per-project private CLAUDE.md registrations."""

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.api.deps import DBSession
from app.core.models.project import ProjectDB
from app.modules.devstack.api.deps import DevstackManager, DevstackViewer
from app.modules.devstack.models.project_context import DevstackProjectContextDB
from app.modules.devstack.services.project_context_service import (
    DevstackProjectContextService,
    DuplicateSlugError,
    ProjectAlreadyLinkedError,
)

router = APIRouter(prefix="/project-contexts", tags=["devstack-contexts"])

SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")


class ProjectContextResponse(BaseModel):
    id: UUID
    slug: str
    project_id: UUID
    project_name: str | None
    description: str | None


class ProjectContextCreate(BaseModel):
    slug: Annotated[str, Field(min_length=1, max_length=64)]
    project_id: UUID
    description: str | None = None

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, v: str) -> str:
        if not SLUG_PATTERN.fullmatch(v):
            raise ValueError("slug must match ^[a-z0-9-]+$")
        return v


class ProjectContextUpdate(BaseModel):
    """Only description is mutable. slug and project_id present as placeholders so
    we can detect them and return 400 (not the Pydantic 422 from extra='forbid')."""
    description: str | None = None
    slug: str | None = None
    project_id: UUID | None = None


def _to_response(
    ctx: DevstackProjectContextDB, project_name: str | None
) -> ProjectContextResponse:
    return ProjectContextResponse(
        id=ctx.id,
        slug=ctx.slug,
        project_id=ctx.project_id,
        project_name=project_name,
        description=ctx.description,
    )


@router.get("", responses={403: {"description": "Not authorized"}})
async def list_project_contexts(
    db: DBSession, user: DevstackViewer
) -> list[ProjectContextResponse]:
    from sqlalchemy import select

    result = await db.execute(
        select(DevstackProjectContextDB, ProjectDB.name)
        .join(ProjectDB, DevstackProjectContextDB.project_id == ProjectDB.id)
        .order_by(DevstackProjectContextDB.slug)
    )
    return [_to_response(ctx, name) for ctx, name in result.all()]


@router.post(
    "",
    status_code=201,
    responses={
        403: {"description": "Not authorized"},
        409: {"description": "Slug already exists or project already linked"},
        422: {"description": "Invalid slug shape"},
    },
)
async def create_project_context(
    body: ProjectContextCreate, db: DBSession, user: DevstackManager
) -> ProjectContextResponse:
    svc = DevstackProjectContextService(db)
    try:
        ctx = await svc.create(
            slug=body.slug,
            project_id=body.project_id,
            description=body.description,
        )
    except DuplicateSlugError:
        raise HTTPException(status_code=409, detail=f"Slug '{body.slug}' already exists")
    except ProjectAlreadyLinkedError:
        raise HTTPException(
            status_code=409,
            detail=f"Project {body.project_id} already has a linked context",
        )

    project = await db.get(ProjectDB, body.project_id)
    if project is None:
        raise HTTPException(status_code=422, detail="Project not found")
    return _to_response(ctx, project.name)


@router.get(
    "/{context_id}",
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Project context not found"},
    },
)
async def get_project_context(
    context_id: UUID, db: DBSession, user: DevstackViewer
) -> ProjectContextResponse:
    svc = DevstackProjectContextService(db)
    ctx = await svc.get(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Project context not found")
    project = await db.get(ProjectDB, ctx.project_id)
    return _to_response(ctx, project.name if project else None)


@router.put(
    "/{context_id}",
    responses={
        400: {"description": "Attempt to change immutable field (slug or project_id)"},
        403: {"description": "Not authorized"},
        404: {"description": "Project context not found"},
    },
)
async def update_project_context(
    context_id: UUID,
    body: ProjectContextUpdate,
    db: DBSession,
    user: DevstackManager,
) -> ProjectContextResponse:
    if body.slug is not None or body.project_id is not None:
        raise HTTPException(status_code=400, detail="slug and project_id are immutable after creation")

    svc = DevstackProjectContextService(db)
    try:
        ctx = await svc.update(context_id, description=body.description)
    except KeyError:
        raise HTTPException(status_code=404, detail="Project context not found")
    project = await db.get(ProjectDB, ctx.project_id)
    return _to_response(ctx, project.name if project else None)


@router.delete(
    "/{context_id}",
    status_code=204,
    responses={
        403: {"description": "Not authorized"},
        404: {"description": "Project context not found"},
    },
)
async def delete_project_context(
    context_id: UUID, db: DBSession, user: DevstackManager
) -> None:
    svc = DevstackProjectContextService(db)
    ctx = await svc.get(context_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Project context not found")
    await svc.delete(context_id)
