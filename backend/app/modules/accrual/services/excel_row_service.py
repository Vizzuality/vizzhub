"""Service for querying parsed Excel rows persisted by the importer."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.models.accrual_alias import AccrualAliasDB
from app.modules.accrual.models.accrual_drift_finding import AccrualDriftFindingDB, DriftKind
from app.modules.accrual.models.accrual_excel_row import AccrualExcelRowDB
from app.modules.accrual.models.accrual_import_run import AccrualImportRunDB


async def _aliases_by_code(db: AsyncSession, excel_codes: list[str]) -> dict[str, ProjectDB]:
    """Return {excel_code: first ProjectDB} for the given codes.

    Picks the earliest alias per code (by created_at) when multiple exist.
    """
    if not excel_codes:
        return {}
    stmt = (
        select(AccrualAliasDB.excel_code, ProjectDB)
        .join(ProjectDB, ProjectDB.id == AccrualAliasDB.project_id)
        .where(AccrualAliasDB.excel_code.in_(excel_codes))
        .order_by(AccrualAliasDB.excel_code, AccrualAliasDB.created_at)
    )
    by_code: dict[str, ProjectDB] = {}
    for code, project in (await db.execute(stmt)).all():
        # Keep the first alias per code (ordered by created_at ascending).
        by_code.setdefault(code, project)
    return by_code


async def latest_run_id(db: AsyncSession) -> UUID | None:
    """Return the ID of the most-recent completed import run, or None."""
    row = (
        await db.execute(
            select(AccrualImportRunDB.id)
            .where(AccrualImportRunDB.completed_at.is_not(None))
            .order_by(AccrualImportRunDB.started_at.desc())
            .limit(1)
        )
    ).first()
    return row[0] if row else None


async def list_rows(
    db: AsyncSession,
    *,
    import_run_id: UUID | None = None,
    excel_code: str | None = None,
    unmatched_only: bool = False,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[tuple[AccrualExcelRowDB, ProjectDB | None]], int]:
    """List Excel rows + alias-mapped project (if any).

    Defaults to most-recent run when ``import_run_id`` is None.

    ``unmatched_only=True`` restricts to rows whose ``excel_code`` appears in an
    unresolved ``missing_tracker`` drift finding from the same run — i.e. the
    importer couldn't resolve them to any tracker project at the time of the
    last run. After mapping via the UI the alias persists, so the row may
    still be in the list (drift not refreshed until re-import) but with a
    populated alias project — useful to spot when multiple Excel codes have
    been mapped to the same project.

    Returns rows sorted so unmapped rows come first (most actionable), then
    mapped rows grouped by project name so siblings are adjacent.
    """
    if import_run_id is None:
        import_run_id = await latest_run_id(db)
        if import_run_id is None:
            return [], 0

    filters = [AccrualExcelRowDB.import_run_id == import_run_id]
    if excel_code:
        filters.append(AccrualExcelRowDB.excel_code.ilike(f"%{excel_code}%"))
    if unmatched_only:
        unmatched_codes_subq = (
            select(AccrualDriftFindingDB.excel_code)
            .where(
                AccrualDriftFindingDB.import_run_id == import_run_id,
                AccrualDriftFindingDB.kind == DriftKind.MISSING_TRACKER.value,
                AccrualDriftFindingDB.resolved_at.is_(None),
                AccrualDriftFindingDB.excel_code.is_not(None),
            )
            .subquery()
        )
        filters.append(AccrualExcelRowDB.excel_code.in_(select(unmatched_codes_subq)))

    stmt = (
        select(AccrualExcelRowDB)
        .where(*filters)
        .order_by(AccrualExcelRowDB.import_run_position)
        .limit(limit)
        .offset(offset)
    )
    count_stmt = select(func.count()).select_from(AccrualExcelRowDB).where(*filters)
    rows = list((await db.execute(stmt)).scalars().all())
    total = (await db.execute(count_stmt)).scalar_one()

    alias_map = await _aliases_by_code(db, [r.excel_code for r in rows])
    paired = [(row, alias_map.get(row.excel_code)) for row in rows]
    # Sort: unmapped (None) first, then by project name ASC so multiple rows
    # mapped to the same project appear consecutive.
    paired.sort(key=lambda x: (x[1] is not None, x[1].name.lower() if x[1] else ""))
    return paired, total


async def list_runs(db: AsyncSession, *, limit: int = 20) -> list[AccrualImportRunDB]:
    """Return the most-recent N import runs (any status)."""
    result = await db.execute(
        select(AccrualImportRunDB).order_by(AccrualImportRunDB.started_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
