"""ISO Docs note endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import desc, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql import func

from app.core.api.deps import DBSession
from app.core.models.user import UserDB
from app.modules.iso_docs.api.deps import IsoDocsEditor
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.note import IsoDocNoteDB
from app.modules.iso_docs.schemas.note import (
    AdminNoteResponse,
    NoteCreate,
    NoteResponse,
    NoteUpdate,
)

router = APIRouter()
logger = structlog.get_logger()


def _user_name_expr(user_alias):
    return func.coalesce(
        func.nullif(
            func.concat_ws(
                " ",
                func.nullif(user_alias.first_name, ""),
                func.nullif(user_alias.last_name, ""),
            ),
            "",
        ),
        user_alias.name,
        user_alias.email,
    )


async def _hydrate_response(db, note: IsoDocNoteDB) -> NoteResponse:
    Creator = aliased(UserDB)
    Doner = aliased(UserDB)
    row = (await db.execute(
        select(_user_name_expr(Creator), _user_name_expr(Doner))
        .select_from(IsoDocNoteDB)
        .outerjoin(Creator, Creator.id == IsoDocNoteDB.created_by_id)
        .outerjoin(Doner, Doner.id == IsoDocNoteDB.done_by_id)
        .where(IsoDocNoteDB.id == note.id)
    )).one()
    resp = NoteResponse.model_validate(note)
    resp.created_by_name = row[0]
    resp.done_by_name = row[1]
    return resp


@router.get("/nodes/{node_id}/notes")
async def list_node_notes(
    node_id: UUID, db: DBSession, _: IsoDocsEditor
) -> list[NoteResponse]:
    node = await db.get(IsoDocNodeDB, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    Creator = aliased(UserDB)
    Doner = aliased(UserDB)
    rows = (await db.execute(
        select(IsoDocNoteDB, _user_name_expr(Creator), _user_name_expr(Doner))
        .outerjoin(Creator, Creator.id == IsoDocNoteDB.created_by_id)
        .outerjoin(Doner, Doner.id == IsoDocNoteDB.done_by_id)
        .where(IsoDocNoteDB.node_id == node_id)
        .order_by(IsoDocNoteDB.done.asc(), desc(IsoDocNoteDB.created_at))
    )).all()

    out: list[NoteResponse] = []
    for note, creator_name, doner_name in rows:
        item = NoteResponse.model_validate(note)
        item.created_by_name = creator_name
        item.done_by_name = doner_name
        out.append(item)
    return out


@router.post(
    "/nodes/{node_id}/notes", status_code=status.HTTP_201_CREATED
)
async def create_note(
    node_id: UUID, data: NoteCreate, db: DBSession, user: IsoDocsEditor
) -> NoteResponse:
    node = await db.get(IsoDocNodeDB, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    note = IsoDocNoteDB(
        node_id=node_id,
        content=data.content,
        created_by_id=user.user_id,
    )
    db.add(note)
    await db.flush()
    await db.refresh(note)
    logger.info(
        "iso_doc_note_created",
        node_id=str(node_id),
        note_id=str(note.id),
        user_id=str(user.user_id),
    )
    return await _hydrate_response(db, note)


@router.patch("/notes/{note_id}")
async def update_note(
    note_id: UUID, data: NoteUpdate, db: DBSession, user: IsoDocsEditor
) -> NoteResponse:
    note = await db.get(IsoDocNoteDB, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if data.content is not None:
        note.content = data.content
    if data.done is not None and data.done != note.done:
        note.done = data.done
        if data.done:
            note.done_at = func.now()
            note.done_by_id = user.user_id
        else:
            note.done_at = None
            note.done_by_id = None

    await db.flush()
    await db.refresh(note)
    logger.info(
        "iso_doc_note_updated",
        note_id=str(note_id),
        done=note.done,
        user_id=str(user.user_id),
    )
    return await _hydrate_response(db, note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: UUID, db: DBSession, user: IsoDocsEditor
) -> Response:
    note = await db.get(IsoDocNoteDB, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    logger.info(
        "iso_doc_note_deleted",
        note_id=str(note_id),
        user_id=str(user.user_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/notes")
async def list_all_notes(
    db: DBSession,
    _: IsoDocsEditor,
    include_done: Annotated[bool, Query()] = False,
) -> list[AdminNoteResponse]:
    Creator = aliased(UserDB)
    Doner = aliased(UserDB)
    stmt = (
        select(
            IsoDocNoteDB,
            IsoDocNodeDB.title.label("node_title"),
            IsoDocNodeDB.slug.label("node_slug"),
            _user_name_expr(Creator),
            _user_name_expr(Doner),
        )
        .join(IsoDocNodeDB, IsoDocNodeDB.id == IsoDocNoteDB.node_id)
        .outerjoin(Creator, Creator.id == IsoDocNoteDB.created_by_id)
        .outerjoin(Doner, Doner.id == IsoDocNoteDB.done_by_id)
        .order_by(IsoDocNodeDB.title.asc(), desc(IsoDocNoteDB.created_at))
    )
    if not include_done:
        stmt = stmt.where(IsoDocNoteDB.done.is_(False))

    rows = (await db.execute(stmt)).all()
    out: list[AdminNoteResponse] = []
    for note, title, slug, creator_name, doner_name in rows:
        base = NoteResponse.model_validate(note)
        base.created_by_name = creator_name
        base.done_by_name = doner_name
        item = AdminNoteResponse(
            **base.model_dump(),
            node_title=title,
            node_slug=slug,
        )
        out.append(item)
    return out
