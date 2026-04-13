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


def _select_notes_with_names(*extra_columns):
    """Build a select with Creator/Doner name joins for IsoDocNoteDB."""
    creator_alias = aliased(UserDB)
    doner_alias = aliased(UserDB)
    return (
        select(
            IsoDocNoteDB,
            _user_name_expr(creator_alias),
            _user_name_expr(doner_alias),
            *extra_columns,
        )
        .outerjoin(creator_alias, creator_alias.id == IsoDocNoteDB.created_by_id)
        .outerjoin(doner_alias, doner_alias.id == IsoDocNoteDB.done_by_id)
    )


def _row_to_response(note: IsoDocNoteDB, creator_name, doner_name) -> NoteResponse:
    resp = NoteResponse.model_validate(note)
    resp.created_by_name = creator_name
    resp.done_by_name = doner_name
    return resp


async def _hydrate_response(db, note: IsoDocNoteDB) -> NoteResponse:
    row = (await db.execute(
        _select_notes_with_names()
        .where(IsoDocNoteDB.id == note.id)
    )).one()
    return _row_to_response(*row)


@router.get(
    "/nodes/{node_id}/notes",
    responses={404: {"description": "Node not found"}},
)
async def list_node_notes(
    node_id: UUID, db: DBSession, _: IsoDocsEditor
) -> list[NoteResponse]:
    node = await db.get(IsoDocNodeDB, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    rows = (await db.execute(
        _select_notes_with_names()
        .where(IsoDocNoteDB.node_id == node_id)
        .order_by(IsoDocNoteDB.done.asc(), desc(IsoDocNoteDB.created_at))
    )).all()
    return [_row_to_response(*row) for row in rows]


@router.post(
    "/nodes/{node_id}/notes",
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Node not found"}},
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


@router.patch(
    "/notes/{note_id}",
    responses={404: {"description": "Note not found"}},
)
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


@router.delete(
    "/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Note not found"}},
)
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
    stmt = (
        _select_notes_with_names(
            IsoDocNodeDB.title.label("node_title"),
            IsoDocNodeDB.slug.label("node_slug"),
        )
        .join(IsoDocNodeDB, IsoDocNodeDB.id == IsoDocNoteDB.node_id)
        .order_by(IsoDocNodeDB.title.asc(), desc(IsoDocNoteDB.created_at))
    )
    if not include_done:
        stmt = stmt.where(IsoDocNoteDB.done.is_(False))

    rows = (await db.execute(stmt)).all()
    return [
        AdminNoteResponse(
            **_row_to_response(note, creator_name, doner_name).model_dump(),
            node_title=title,
            node_slug=slug,
        )
        for note, creator_name, doner_name, title, slug in rows
    ]
