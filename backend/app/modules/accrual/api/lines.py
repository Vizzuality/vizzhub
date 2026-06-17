"""HTTP endpoints for accrual line CRUD and project links."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.core.sql_helpers import user_display_name_expr
from app.modules.accrual.models.accrual_line import AccrualLineDB
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from app.modules.accrual.schemas.accrual_line import LineCreate, LineProjectLink, LineUpdate
from app.modules.accrual.services import cell_service, line_service, period_service

router = APIRouter()

_LINE_NOT_FOUND = "Line not found"

AccrualViewer = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_VIEW))]
AccrualManager = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_MANAGE))]


def _parse_user_id(token: TokenData) -> UUID | None:
    return UUID(token.user_id) if token.user_id else None


async def _linked_projects(db: DBSession, line_id: UUID) -> list[dict]:
    pm = aliased(UserDB)
    rows = (
        await db.execute(
            select(ProjectDB, user_display_name_expr(pm).label("pm"))
            .join(AccrualLineProjectDB, AccrualLineProjectDB.project_id == ProjectDB.id)
            .outerjoin(pm, ProjectDB.project_manager_id == pm.id)
            .where(AccrualLineProjectDB.line_id == line_id)
        )
    ).all()
    return [
        {
            "id": str(project.id),
            "code": project.code,
            "name": project.name,
            "status": project.status,
            "project_manager_id": (
                str(project.project_manager_id) if project.project_manager_id else None
            ),
            "project_manager_name": pm_name,
        }
        for project, pm_name in rows
    ]


async def _serialize_line(db: DBSession, line: AccrualLineDB) -> dict:
    period_rate = await period_service.resolve_line_period_rate(db, line)
    return {
        "id": str(line.id),
        "name": line.name,
        "source": line.source,
        "excel_code": line.excel_code,
        "value_eur": str(line.value_eur),
        "value_orig": str(line.value_orig) if line.value_orig is not None else None,
        "currency": line.currency,
        "rate": str(line.rate) if line.rate is not None else None,
        "period_rate": period_rate,
        "window_start": line.window_start.isoformat() if line.window_start else None,
        "window_end": line.window_end.isoformat() if line.window_end else None,
        "projects": await _linked_projects(db, line.id),
    }


async def _get_line_or_404(db: DBSession, line_id: UUID) -> AccrualLineDB:
    line = await db.get(AccrualLineDB, line_id)
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_LINE_NOT_FOUND)
    return line


@router.post("/lines", status_code=status.HTTP_201_CREATED)
async def create_line(payload: LineCreate, db: DBSession, user: AccrualManager) -> dict:
    """Create a manual revenue-recognition line, optionally linked to projects."""
    line = await line_service.create_line(
        db,
        name=payload.name,
        value_eur=payload.value_eur,
        value_orig=payload.value_orig,
        currency=payload.currency,
        window_start=payload.window_start,
        window_end=payload.window_end,
        project_ids=payload.project_ids,
        created_by=_parse_user_id(user),
    )
    return await _serialize_line(db, line)


@router.get("/lines/{line_id}", responses={404: {"description": "Line not found"}})
async def get_line(line_id: UUID, db: DBSession, _: AccrualViewer) -> dict:
    """Return one line with its linked projects (the line-editor detail view)."""
    line = await _get_line_or_404(db, line_id)
    return await _serialize_line(db, line)


@router.patch(
    "/lines/{line_id}",
    responses={
        404: {"description": "Line not found"},
        409: {"description": "Frozen cell would fall outside the new window"},
    },
)
async def update_line(line_id: UUID, payload: LineUpdate, db: DBSession, _: AccrualManager) -> dict:
    """Patch a line's editable fields. Changing the window moves the line's cells with
    it (orphaned months deleted, value redistributed across the new window) — rejected
    with 409 if that would orphan a frozen cell. ``rate`` is the FX override: setting it
    (or clearing with null) recomputes value_eur and redistributes the open months."""
    fields = payload.model_dump(exclude_unset=True)
    rate_present = "rate" in fields
    rate_value = fields.pop("rate", None)

    existing = await _get_line_or_404(db, line_id)
    window_changed = (
        "window_start" in fields and fields["window_start"] != existing.window_start
    ) or ("window_end" in fields and fields["window_end"] != existing.window_end)

    if fields:
        line = await line_service.update_line(db, line_id=line_id, fields=fields)
        if line is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_LINE_NOT_FOUND)
    else:
        line = existing

    if window_changed:
        try:
            await cell_service.reconcile_line_window(db, line_id=line_id)
        except cell_service.CellFrozenError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if rate_present:
        await cell_service.set_line_rate(db, line_id=line_id, rate=rate_value)
        line = await _get_line_or_404(db, line_id)

    return await _serialize_line(db, line)


@router.delete(
    "/lines/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Line not found"}},
)
async def delete_line(line_id: UUID, db: DBSession, _: AccrualManager) -> None:
    """Delete a line; its cells and project links cascade."""
    if not await line_service.delete_line(db, line_id=line_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_LINE_NOT_FOUND)


@router.post(
    "/lines/{line_id}/projects",
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Line not found"}},
)
async def link_project(
    line_id: UUID, payload: LineProjectLink, db: DBSession, _: AccrualManager
) -> dict:
    """Link a project to the line (idempotent)."""
    line = await _get_line_or_404(db, line_id)
    await line_service.link_project(db, line_id=line_id, project_id=payload.project_id)
    return await _serialize_line(db, line)


@router.delete(
    "/lines/{line_id}/projects/{project_id}",
    responses={404: {"description": "Line or link not found"}},
)
async def unlink_project(line_id: UUID, project_id: UUID, db: DBSession, _: AccrualManager) -> dict:
    """Unlink a project from the line."""
    line = await _get_line_or_404(db, line_id)
    if not await line_service.unlink_project(db, line_id=line_id, project_id=project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    return await _serialize_line(db, line)
