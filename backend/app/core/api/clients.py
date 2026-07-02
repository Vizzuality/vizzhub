"""Client CRUD endpoints (core). Read=portfolio:view, write=portfolio:manage."""

import re
import unicodedata
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.api.deps import DBSession, limiter
from app.core.auth import TokenData
from app.core.models.client import Client, ClientCreate, ClientDB, ClientUpdate
from app.core.models.project import ProjectDB
from app.core.permissions import Action, require_permission
from app.core.services.client_service import merge_clients

PortfolioViewer = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_VIEW))]
PortfolioManager = Annotated[TokenData, Depends(require_permission(Action.PORTFOLIO_MANAGE))]
ProjectManager = Annotated[TokenData, Depends(require_permission(Action.PROJECTS_MANAGE))]

router = APIRouter()
logger = structlog.get_logger()


def slugify(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def _clean(value: str | None) -> str | None:
    """Normalize an optional string: strip whitespace, coerce empty to None."""
    return (value or "").strip() or None


async def _code_taken(db: DBSession, code: str, exclude_id: UUID | None = None) -> bool:
    """Whether another client already uses this (non-null) code."""
    stmt = select(ClientDB.id).where(ClientDB.code == code)
    if exclude_id is not None:
        stmt = stmt.where(ClientDB.id != exclude_id)
    return (await db.execute(stmt)).first() is not None


class ClientListResponse(BaseModel):
    items: list[Client]
    total: int
    page: int
    page_size: int


class ClientOption(BaseModel):
    id: UUID
    name: str
    code: str | None = None


@router.get("")
@limiter.limit("100/minute")
async def list_clients(
    request: Request,
    current_user: PortfolioViewer,
    db: DBSession,
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ClientListResponse:
    count_subq = (
        select(ProjectDB.client_id, func.count().label("n"))
        .group_by(ProjectDB.client_id)
        .subquery()
    )
    stmt = select(ClientDB, func.coalesce(count_subq.c.n, 0)).outerjoin(
        count_subq, count_subq.c.client_id == ClientDB.id
    )
    if search:
        stmt = stmt.where(ClientDB.name.ilike(f"%{search}%"))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    stmt = stmt.order_by(ClientDB.name).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).all()
    items = []
    for client_row, n in rows:
        model = Client.model_validate(client_row)
        model.project_count = int(n)
        items.append(model)
    return ClientListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/options")
@limiter.limit("100/minute")
async def list_client_options(
    request: Request,
    current_user: ProjectManager,
    db: DBSession,
) -> list[ClientOption]:
    """Flat active-client list for the project edit form selector."""
    rows = (
        await db.execute(
            select(ClientDB.id, ClientDB.name, ClientDB.code)
            .where(ClientDB.is_active.is_(True))
            .order_by(ClientDB.name)
        )
    ).all()
    return [ClientOption(id=r.id, name=r.name, code=r.code) for r in rows]


@router.post("", status_code=201, responses={409: {"description": "Duplicate client"}})
@limiter.limit("30/minute")
async def create_client(
    request: Request, current_user: PortfolioManager, db: DBSession, payload: ClientCreate
) -> Client:
    slug = slugify(payload.name)
    existing = await db.execute(select(ClientDB).where(ClientDB.slug == slug))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A client with this name already exists")
    code = _clean(payload.code)
    if code is not None and await _code_taken(db, code):
        raise HTTPException(status_code=409, detail="A client with this code already exists")
    obj = ClientDB(
        name=payload.name.strip(),
        slug=slug,
        code=code,
        primary_contact=_clean(payload.primary_contact),
    )
    db.add(obj)
    await db.flush()
    await db.refresh(obj)
    logger.info("client_created", client_id=str(obj.id), slug=slug, user_id=current_user.user_id)
    model = Client.model_validate(obj)
    model.project_count = 0
    return model


@router.patch(
    "/{client_id}",
    responses={404: {"description": "Not found"}, 409: {"description": "Duplicate client"}},
)
@limiter.limit("30/minute")
async def update_client(
    request: Request,
    current_user: PortfolioManager,
    db: DBSession,
    client_id: UUID,
    payload: ClientUpdate,
) -> Client:
    obj = (await db.execute(select(ClientDB).where(ClientDB.id == client_id))).scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404, detail="Client not found")
    if payload.name is not None:
        new_slug = slugify(payload.name)
        collision = (
            await db.execute(
                select(ClientDB).where(ClientDB.slug == new_slug, ClientDB.id != client_id)
            )
        ).scalar_one_or_none()
        if collision is not None:
            raise HTTPException(status_code=409, detail="A client with this name already exists")
        obj.name = payload.name.strip()
        obj.slug = new_slug
    if "code" in payload.model_fields_set:
        new_code = _clean(payload.code)
        if new_code is not None and await _code_taken(db, new_code, exclude_id=client_id):
            raise HTTPException(status_code=409, detail="A client with this code already exists")
        obj.code = new_code
    if "primary_contact" in payload.model_fields_set:
        obj.primary_contact = _clean(payload.primary_contact)
    if payload.is_active is not None:
        obj.is_active = payload.is_active
    await db.flush()
    await db.refresh(obj)
    logger.info("client_updated", client_id=str(obj.id), user_id=current_user.user_id)
    return Client.model_validate(obj)


class MergeRequest(BaseModel):
    source_ids: list[UUID]


class MergeResponse(BaseModel):
    merged_projects: int
    target: Client


@router.post("/{target_id}/merge", responses={400: {"description": "Invalid merge"}})
@limiter.limit("20/minute")
async def merge_clients_endpoint(
    request: Request,
    current_user: PortfolioManager,
    db: DBSession,
    target_id: UUID,
    payload: MergeRequest,
) -> MergeResponse:
    try:
        moved = await merge_clients(db, target_id=target_id, source_ids=payload.source_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.flush()
    target = (await db.execute(select(ClientDB).where(ClientDB.id == target_id))).scalar_one()
    return MergeResponse(merged_projects=moved, target=Client.model_validate(target))
