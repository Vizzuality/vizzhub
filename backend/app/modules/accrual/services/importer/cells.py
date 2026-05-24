"""Apply Excel rows to DB project cells (Phase 3: Render).

Two flows depending on cardinality:
- Single-project: one Excel row → one DB project. Cells in range are written
  as overrides; budget is redistributed across remaining months.
- Multi-project: one Excel row → N DB projects sharing the code. Each cell
  is imputed to the project whose date range contains (year, month).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.project_accrual_cell import CellSource, ProjectAccrualCellDB
from app.modules.accrual.services import cell_service
from app.modules.accrual.services.importer.parser import SpreadsheetRow


def cell_in_range(y: int, m: int, project) -> bool:
    """True iff (year, month) falls inside [project.start_date, project.end_date]."""
    if not project.start_date or not project.end_date:
        return False
    return (
        (project.start_date.year, project.start_date.month)
        <= (y, m)
        <= (
            project.end_date.year,
            project.end_date.month,
        )
    )


async def apply_excel_overrides(
    db: AsyncSession,
    *,
    project,
    overrides: list[tuple[int, int, Decimal]],
) -> int:
    """Write Excel cells as overrides, skipping already-frozen cells.

    Cells are marked ``source='excel'`` so the UI can distinguish them from
    team-budget fallback or manual edits.
    """
    existing_result = await db.execute(
        select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.project_id == project.id)
    )
    existing_by_ym = {(c.year, c.month): c for c in existing_result.scalars().all()}
    written = 0
    for y, m, amount in overrides:
        existing_cell = existing_by_ym.get((y, m))
        if existing_cell is not None and existing_cell.is_frozen:
            continue
        await cell_service.set_cell_amount(
            db,
            project_id=project.id,
            year=y,
            month=m,
            amount=amount,
            source=CellSource.EXCEL,
        )
        written += 1
    return written


async def apply_single_project(
    db: AsyncSession,
    *,
    row: SpreadsheetRow,
    project,
    report: dict,
) -> None:
    """Excel row → exactly one DB project. Apply cells in range; report orphans."""
    if project.original_budget is None and row.value:
        project.original_budget = row.value
        report["original_budget_set"] += 1
    await db.flush()

    excel_start_outside = row.start_date is not None and row.start_date < project.start_date
    excel_end_outside = row.end_date is not None and row.end_date > project.end_date

    in_range_overrides: list[tuple[int, int, Decimal]] = []
    cells_orphaned = 0
    for (y, m), amount in row.monthly.items():
        if cell_in_range(y, m, project):
            in_range_overrides.append((y, m, amount))
        else:
            cells_orphaned += 1

    written = await apply_excel_overrides(db, project=project, overrides=in_range_overrides)
    report["overrides_imported"] += written

    await cell_service.redistribute_for_project(
        db, project_id=project.id, full_range=True, source=CellSource.EXCEL
    )

    if excel_start_outside or excel_end_outside or cells_orphaned > 0:
        report["date_mismatches"].append(
            {
                "code": project.code,
                "project_id": str(project.id),
                "name": project.name,
                "db_start": str(project.start_date),
                "db_end": str(project.end_date),
                "excel_start": str(row.start_date) if row.start_date else None,
                "excel_end": str(row.end_date) if row.end_date else None,
                "cells_orphaned": cells_orphaned,
            }
        )


async def apply_multi_project(
    db: AsyncSession,
    *,
    row: SpreadsheetRow,
    projects: list,
    report: dict,
) -> None:
    """Excel row → N DB projects sharing the code (an "extension group").

    Each Excel monthly cell is imputed to the project whose date range contains
    (year, month). If 0 projects cover it → orphan; if >1 cover it → ambiguous
    (reported, NOT imputed — would distort revenue forecasting). ``original_budget``
    is split proportionally per project's share of EUR imputed; ``project.budget``
    is never touched (team-managed).
    """
    imputed_per_project: dict = {p.id: [] for p in projects}
    orphan_cells: list[tuple[int, int, Decimal]] = []
    ambiguous_cells: list[tuple[int, int, Decimal, list[str]]] = []
    for (y, m), amount in row.monthly.items():
        covering = [p for p in projects if cell_in_range(y, m, p)]
        if not covering:
            orphan_cells.append((y, m, amount))
        elif len(covering) == 1:
            imputed_per_project[covering[0].id].append((y, m, amount))
        else:
            ambiguous_cells.append((y, m, amount, [str(p.id) for p in covering]))

    for project in projects:
        cells = imputed_per_project[project.id]
        if cells:
            written = await apply_excel_overrides(db, project=project, overrides=cells)
            report["overrides_imported"] += written

    total_value_eur = row.value_eur or Decimal("0")
    for project in projects:
        if project.original_budget is not None or total_value_eur == 0 or not row.value:
            continue
        share_eur = sum((a for _, _, a in imputed_per_project[project.id]), Decimal("0"))
        if share_eur <= 0:
            continue
        ratio = share_eur / total_value_eur
        project.original_budget = (row.value * ratio).quantize(Decimal("0.01"))
        report["original_budget_set"] += 1
    await db.flush()

    for project in projects:
        await cell_service.redistribute_for_project(
            db, project_id=project.id, full_range=True, source=CellSource.EXCEL
        )

    report["multi_project_groups"].append(
        {
            "code": row.code,
            "excel_value_eur": str(row.value_eur),
            "projects": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "db_start": str(p.start_date) if p.start_date else None,
                    "db_end": str(p.end_date) if p.end_date else None,
                    "cells_imputed": len(imputed_per_project[p.id]),
                    "eur_imputed": str(
                        sum((a for _, _, a in imputed_per_project[p.id]), Decimal("0"))
                    ),
                }
                for p in projects
            ],
            "orphan_cells": len(orphan_cells),
            "ambiguous_cells": len(ambiguous_cells),
        }
    )
