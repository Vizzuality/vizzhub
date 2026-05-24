"""HTTP endpoints for accrual Excel rows + import runs.

Mounted under ``/api/accrual/excel-rows``. Reads require ``ACCRUAL_VIEW``.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.modules.accrual.schemas.accrual_excel_row import (
    AccrualExcelRow,
    AccrualExcelRowsResponse,
    AccrualImportRun,
)
from app.modules.accrual.services import excel_row_service

router = APIRouter()

AccrualViewer = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_VIEW))]


@router.get(
    "",
    response_model=AccrualExcelRowsResponse,
    responses={403: {"description": "Insufficient permissions"}},
)
async def list_excel_rows(
    _user: AccrualViewer,
    db: DBSession,
    import_run_id: Annotated[UUID | None, Query()] = None,
    excel_code: Annotated[str | None, Query()] = None,
    unmatched_only: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AccrualExcelRowsResponse:
    """List Excel rows from a given (or the latest) import run.

    ``unmatched_only=true`` filters to rows whose code did not resolve to any
    tracker project (i.e. has an open ``missing_tracker`` drift finding for
    the same run).
    """
    rows, total = await excel_row_service.list_rows(
        db,
        import_run_id=import_run_id,
        excel_code=excel_code,
        unmatched_only=unmatched_only,
        limit=limit,
        offset=offset,
    )
    items = []
    for row, project in rows:
        item = AccrualExcelRow.model_validate(row)
        if project is not None:
            item.alias_project_id = project.id
            item.alias_project_name = project.name
            item.alias_project_code = project.code
        items.append(item)
    return AccrualExcelRowsResponse(
        items=items,
        total=total,
        import_run_id=import_run_id or (await excel_row_service.latest_run_id(db)),
    )


@router.get(
    "/runs",
    response_model=list[AccrualImportRun],
    responses={403: {"description": "Insufficient permissions"}},
)
async def list_import_runs(
    _user: AccrualViewer,
    db: DBSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AccrualImportRun]:
    """Return the most-recent N import runs."""
    runs = await excel_row_service.list_runs(db, limit=limit)
    return [AccrualImportRun.model_validate(r) for r in runs]
