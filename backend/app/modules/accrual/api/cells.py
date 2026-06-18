"""HTTP endpoints for accrual cells (line-keyed) and the grid view."""

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.core.api.deps import DBSession
from app.core.auth import TokenData
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.permissions.actions import Action
from app.core.permissions.dependencies import require_permission
from app.core.services.exchange_rate_service import currency_to_code
from app.core.sql_helpers import user_display_name_expr
from app.modules.accrual.models.accrual_cell import AccrualCellDB
from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from app.modules.accrual.schemas.accrual_cell import (
    BulkCellsRequest,
    CellUpdate,
    LineCellUpsert,
    RedistributeRequest,
)
from app.modules.accrual.services import cell_service, period_service

logger = structlog.get_logger()
router = APIRouter()

AccrualViewer = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_VIEW))]
AccrualManager = Annotated[TokenData, Depends(require_permission(Action.ACCRUAL_MANAGE))]


def _parse_user_id(token: TokenData) -> UUID | None:
    return UUID(token.user_id) if token.user_id else None


# Health thresholds (diff_pct).
_HEALTH_WARNING_THRESHOLD = Decimal("5")
_HEALTH_CRITICAL_THRESHOLD = Decimal("20")

# Upper bound on the grid's year span — caps the user-controlled range() so a
# request like year_from=0&year_to=999999 can't build a giant months list (DoS).
_MAX_GRID_YEAR_SPAN = 50


def _diff_eur_pct(
    budget: Decimal | None, sum_cells: Decimal
) -> tuple[Decimal | None, Decimal | None]:
    if budget is None or budget == 0:
        return None, None
    diff_eur = (sum_cells - budget).quantize(Decimal("0.01"))
    diff_pct = (abs(diff_eur) / budget * Decimal("100")).quantize(Decimal("0.01"))
    return diff_eur, diff_pct


def _serialize(cell: AccrualCellDB) -> dict:
    """Cells are EUR-only, so ``amount`` IS the EUR figure. Frozen cells expose
    ``frozen_eur_amount`` as the immutable snapshot captured at period close."""
    return {
        "id": str(cell.id),
        "line_id": str(cell.line_id),
        "year": cell.year,
        "month": cell.month,
        "amount": str(cell.amount),
        "is_manual_override": cell.is_manual_override,
        "is_frozen": cell.is_frozen,
        "frozen_at": cell.frozen_at.isoformat() if cell.frozen_at else None,
        "frozen_eur_amount": (
            str(cell.frozen_eur_amount) if cell.frozen_eur_amount is not None else None
        ),
        "eur_amount": str(cell.amount),
        "source": cell.source,
        "updated_at": cell.updated_at.isoformat(),
    }


def _line_health(value_eur: Decimal | None, sum_cells: Decimal) -> dict:
    """A line's health = how close its scheduled cells are to its declared value.

    For Excel lines the cells are the CEO's verbatim monthly forecast and
    ``value_eur`` is the contract/total — a gap is a real "not fully scheduled"
    signal, not an error. Compared in the SAME currency (both EUR, same source),
    so there is no FX contamination.
    """
    diff_eur, diff_pct = _diff_eur_pct(value_eur, sum_cells)
    if value_eur is None or value_eur == 0:
        status_str = "no_data"
    elif diff_pct is not None and diff_pct > _HEALTH_CRITICAL_THRESHOLD:
        status_str = "critical"
    elif diff_pct is not None and diff_pct > _HEALTH_WARNING_THRESHOLD:
        status_str = "warning"
    else:
        status_str = "ok"
    return {
        "status": status_str,
        "diff_eur": str(diff_eur) if diff_eur is not None else None,
        "diff_pct": float(diff_pct) if diff_pct is not None else None,
    }


def _data_quality_note(line: AccrualLineDB) -> str | None:
    """Flag a foreign-currency Excel line missing its original amount.

    A non-EUR Excel line should carry the original-currency amount it was billed
    in. When it does not, the source mis-recorded the amount/rate (e.g. a USD
    rate on a GBP contract) and the provenance was cleared. The EUR figure stays
    authoritative — this note explains the blank original column.
    """
    if (
        line.source == LineSource.EXCEL
        and line.currency not in (None, "EUR")
        and line.value_orig is None
    ):
        return (
            "Original amount unreliable: the source recorded a wrong currency or "
            "rate, so it was cleared. The EUR figure is authoritative."
        )
    return None


def _serialize_line_project(project: ProjectDB, pm_name: str | None) -> dict:
    return {
        "id": str(project.id),
        "code": project.code,
        "name": project.name,
        "status": project.status,
        "project_manager_id": (
            str(project.project_manager_id) if project.project_manager_id else None
        ),
        "project_manager_name": pm_name,
    }


def _dates_diverged(line: AccrualLineDB, projects: list[tuple[ProjectDB, str | None]]) -> bool:
    """True when a single-project DERIVED (team_budget) line's window no longer
    matches the project's contract dates (R6). Only team_budget lines derive from
    project dates; Excel lines set their window from the Excel month span (so a
    difference there is by design, not a divergence) and unlinked / multi-project
    lines have no single contract to compare against."""
    if line.source != LineSource.TEAM_BUDGET.value or len(projects) != 1:
        return False
    project = projects[0][0]
    return line.window_start != project.start_date or line.window_end != project.end_date


async def _period_rates_for_lines(
    db: DBSession, lines: list[AccrualLineDB]
) -> dict[UUID, str | None]:
    """line_id -> resolved period rate string (or None). Resolves once per distinct
    (currency-code, window-start month) so the grid does not issue N lookups."""
    cache: dict[tuple[str, int, int], Decimal | None] = {}
    out: dict[UUID, str | None] = {}
    for line in lines:
        if not line.currency or line.window_start is None:
            out[line.id] = None
            continue
        code = currency_to_code(line.currency)
        if code == "EUR":
            out[line.id] = None
            continue
        key = (code, line.window_start.year, line.window_start.month)
        if key not in cache:
            cache[key] = await period_service.resolve_rate(db, code=code, as_of=line.window_start)
        resolved = cache[key]
        out[line.id] = str(resolved) if resolved is not None else None
    return out


def _serialize_grid_line(
    line: AccrualLineDB,
    projects: list[tuple[ProjectDB, str | None]],
    *,
    sum_cells: Decimal,
    period_rate: str | None,
) -> dict:
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
        "projects": [_serialize_line_project(p, pm_name) for p, pm_name in projects],
        "health": _line_health(line.value_eur, sum_cells),
        "data_quality_note": _data_quality_note(line),
        "dates_diverged": _dates_diverged(line, projects),
    }


def _line_passes_filters(
    linked: list[tuple[ProjectDB, str | None]],
    source: str,
    *,
    status: str | None,
    project_manager_id: UUID | None,
    source_filter: str | None,
) -> bool:
    """A line passes when every active filter matches. status/pm match any linked
    project (so unlinked lines drop out once either is set)."""
    if status is not None and not any(p.status == status for p, _ in linked):
        return False
    if project_manager_id is not None and not any(
        p.project_manager_id == project_manager_id for p, _ in linked
    ):
        return False
    return source_filter is None or source == source_filter


def _compute_bounds(lines: list[AccrualLineDB]) -> dict | None:
    """Min/max window year across the given lines, or None when none are dated."""
    bounds_min = min(
        (line.window_start.year for line in lines if line.window_start is not None),
        default=None,
    )
    bounds_max = max(
        (line.window_end.year for line in lines if line.window_end is not None),
        default=None,
    )
    if bounds_min is None or bounds_max is None:
        return None
    return {"min_year": bounds_min, "max_year": bounds_max}


def _window_overlaps_years(line: AccrualLineDB, year_from: int, year_to: int) -> bool:
    """True when the line's window intersects [year_from, year_to]. Undated → excluded."""
    if line.window_start is None or line.window_end is None:
        return False
    return line.window_start <= date(year_to, 12, 31) and line.window_end >= date(year_from, 1, 1)


@router.get(
    "/grid",
    responses={400: {"description": "invalid year range (year_to < year_from or span too large)"}},
)
async def get_grid(
    db: DBSession,
    _: AccrualViewer,
    year_from: int,
    year_to: int,
    status: str | None = None,
    currency: str | None = None,
    project_manager_id: UUID | None = None,
    source: str | None = None,
) -> dict:
    """Accrual grid: rows are **lines** (the revenue-recognition unit), not projects.

    Each line carries its linked projects as tags (0..N), its editable window, its
    value, and a health badge (Σcells vs value_eur, same-currency so no FX noise).
    Cells are keyed by ``line_id``.

    Filtering:
    - ``year_from`` / ``year_to``: keep lines whose window overlaps the span.
    - ``status`` / ``project_manager_id``: match on any LINKED project; unlinked
      lines are excluded when either is set.
    - ``currency``: match the line's own currency (Excel lines); lines without a
      currency are excluded when it is set.
    - ``source``: ``excel`` | ``team_budget`` | ``manual``.

    ``bounds`` (min/max window year over the status+pm+source-filtered set) and
    ``available_currencies`` drive the toolbar.
    """
    if year_to < year_from:
        raise HTTPException(status_code=400, detail="year_to must be >= year_from")
    if year_to - year_from > _MAX_GRID_YEAR_SPAN:
        raise HTTPException(
            status_code=400,
            detail=f"year span must not exceed {_MAX_GRID_YEAR_SPAN} years",
        )

    pm = aliased(UserDB)
    lines = list((await db.execute(select(AccrualLineDB))).scalars().all())

    # line_id -> [(project, pm_name)]
    lp_rows = (
        await db.execute(
            select(AccrualLineProjectDB.line_id, ProjectDB, user_display_name_expr(pm).label("pm"))
            .join(ProjectDB, ProjectDB.id == AccrualLineProjectDB.project_id)
            .outerjoin(pm, ProjectDB.project_manager_id == pm.id)
        )
    ).all()
    projects_by_line: dict[UUID, list[tuple[ProjectDB, str | None]]] = {}
    for line_id, project, pm_name in lp_rows:
        projects_by_line.setdefault(line_id, []).append((project, pm_name))

    filtered = [
        line
        for line in lines
        if _line_passes_filters(
            projects_by_line.get(line.id, []),
            line.source,
            status=status,
            project_manager_id=project_manager_id,
            source_filter=source,
        )
    ]

    # bounds + available currencies reflect the status/pm/source set, BEFORE the
    # year/currency narrowing — they drive the toolbar's full navigable range.
    bounds = _compute_bounds(filtered)
    available_currencies = sorted(
        {currency_to_code(line.currency) for line in filtered if line.currency}
    )

    if currency is not None:
        target_code = currency_to_code(currency)
        filtered = [
            line
            for line in filtered
            if line.currency and currency_to_code(line.currency) == target_code
        ]

    filtered = [line for line in filtered if _window_overlaps_years(line, year_from, year_to)]
    line_ids = [line.id for line in filtered]

    # Per-line total across ALL cells so the health badge is year-navigation stable.
    sum_by_line: dict[UUID, Decimal] = {}
    if line_ids:
        agg = await db.execute(
            select(
                AccrualCellDB.line_id,
                func.coalesce(func.sum(AccrualCellDB.amount), 0).label("total"),
            )
            .where(AccrualCellDB.line_id.in_(line_ids))
            .group_by(AccrualCellDB.line_id)
        )
        for lid, total in agg.all():
            sum_by_line[lid] = Decimal(str(total))

    period_rate_by_line = await _period_rates_for_lines(db, filtered)
    lines_serialised = [
        _serialize_grid_line(
            line,
            projects_by_line.get(line.id, []),
            sum_cells=sum_by_line.get(line.id, Decimal("0")),
            period_rate=period_rate_by_line.get(line.id),
        )
        for line in filtered
    ]

    cells_serialised: list[dict] = []
    if line_ids:
        cells_result = await db.execute(
            select(AccrualCellDB)
            .where(
                AccrualCellDB.line_id.in_(line_ids),
                AccrualCellDB.year >= year_from,
                AccrualCellDB.year <= year_to,
            )
            .order_by(
                AccrualCellDB.line_id,
                AccrualCellDB.year,
                AccrualCellDB.month,
            )
        )
        cells_serialised = [_serialize(c) for c in cells_result.scalars().all()]

    # Loop count is clamped to a constant (not the raw user span) so the bound is
    # provably bounded regardless of input — the span guard above already rejects
    # oversized ranges, this keeps the iteration count out of user control (S6680).
    year_count = min(year_to - year_from + 1, _MAX_GRID_YEAR_SPAN + 1)
    months = [
        {"year": year_from + offset, "month": month}
        for offset in range(year_count)
        for month in range(1, 13)
    ]
    return {
        "lines": lines_serialised,
        "cells": cells_serialised,
        "months": months,
        "bounds": bounds,
        "available_currencies": available_currencies,
    }


@router.patch(
    "/cells/{cell_id}",
    responses={
        404: {"description": "Cell not found"},
        409: {"description": "Cell is frozen"},
    },
)
async def patch_cell(
    cell_id: UUID,
    payload: CellUpdate,
    db: DBSession,
    user: AccrualManager,
) -> dict:
    """Set an existing cell to an explicit amount, marking it a manual override."""
    cell = await db.get(AccrualCellDB, cell_id)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    if cell.line_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cell is not attached to a line"
        )
    try:
        await cell_service.set_cell_amount_by_line(
            db,
            line_id=cell.line_id,
            year=cell.year,
            month=cell.month,
            amount=payload.amount,
            user_id=_parse_user_id(user),
        )
    except cell_service.CellFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.refresh(cell)
    return _serialize(cell)


@router.put(
    "/lines/{line_id}/cells",
    responses={
        404: {"description": "Line not found"},
        409: {"description": "Cell is frozen"},
    },
)
async def upsert_line_cell(
    line_id: UUID,
    payload: LineCellUpsert,
    db: DBSession,
    user: AccrualManager,
) -> dict:
    """Create or update a cell on a line at (year, month) — the inline-edit path.

    Keyed by ``line_id`` so it works for multi-project and unlinked lines.
    Editing a previously-empty month creates the cell.
    """
    line = await db.get(AccrualLineDB, line_id)
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line not found")
    try:
        cell = await cell_service.set_cell_amount_by_line(
            db,
            line_id=line_id,
            year=payload.year,
            month=payload.month,
            amount=payload.amount,
            user_id=_parse_user_id(user),
        )
    except cell_service.CellFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize(cell)


@router.post(
    "/lines/{line_id}/redistribute",
    responses={404: {"description": "Line not found"}},
)
async def redistribute_line(
    line_id: UUID,
    payload: RedistributeRequest,
    db: DBSession,
    user: AccrualManager,
) -> dict:
    """Spread the line's value_eur uniformly across its window's mutable months."""
    line = await db.get(AccrualLineDB, line_id)
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line not found")
    cells_updated = await cell_service.redistribute_for_line(
        db,
        line_id=line_id,
        force=payload.force,
    )
    logger.info(
        "accrual_redistribute_line_endpoint",
        line_id=str(line_id),
        cells_updated=cells_updated,
        force=payload.force,
        user_id=user.user_id,
    )
    return {"cells_updated": cells_updated}


@router.delete(
    "/cells/{cell_id}/override",
    responses={
        404: {"description": "Cell not found"},
        409: {"description": "Cell is frozen"},
    },
)
async def delete_override(
    cell_id: UUID,
    db: DBSession,
    user: AccrualManager,
) -> dict:
    """Clear a manual override and redistribute the freed budget across remaining months."""
    cell = await db.get(AccrualCellDB, cell_id)
    if cell is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell not found")
    if cell.line_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Cell is not attached to a line"
        )
    try:
        await cell_service.clear_override_by_line(
            db,
            line_id=cell.line_id,
            year=cell.year,
            month=cell.month,
        )
    except cell_service.CellFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await db.refresh(cell)
    logger.info(
        "accrual_override_cleared",
        cell_id=str(cell.id),
        line_id=str(cell.line_id),
        user_id=user.user_id,
    )
    return _serialize(cell)


@router.post(
    "/cells/bulk",
    responses={409: {"description": "Bulk write hit a frozen cell — entire batch reverted"}},
)
async def bulk_cells(
    payload: BulkCellsRequest,
    db: DBSession,
    user: AccrualManager,
) -> dict:
    """Apply many cell overrides atomically. A frozen cell aborts the whole batch."""
    try:
        results = await cell_service.bulk_set_cells_by_line(
            db,
            updates=[u.model_dump() for u in payload.updates],
            user_id=_parse_user_id(user),
        )
    except cell_service.CellFrozenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    logger.info(
        "accrual_bulk_cells_endpoint",
        count=len(results),
        user_id=user.user_id,
    )
    return {"updated": len(results)}
