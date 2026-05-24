"""5-phase accrual importer pipeline.

Phase 1 — Snapshot: parse Excel → persist accrual_excel_rows.
Phase 2 — Resolve: for each Excel row, find tracker projects (alias > code > prefix).
Phase 3 — Render: apply cells (Excel-derived) + team_budget fallback for unmatched projects.
Phase 4 — Drift detection: emit accrual_drift_findings.
Phase 5 — Report: stamp accrual_import_run with totals.

Manual aliases (``accrual_aliases``) override the code-matching resolution. The
pipeline reads them at the start of Phase 2 and merges them with the auto-matched
candidates. Manual aliases take precedence (i.e. the auto-matched candidates are
discarded for any excel_code that has at least one alias).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.models.accrual_alias import AccrualAliasDB
from app.modules.accrual.models.accrual_import_run import AccrualImportRunDB
from app.modules.accrual.models.project_accrual_cell import CellSource, ProjectAccrualCellDB
from app.modules.accrual.services import cell_service
from app.modules.accrual.services.importer.cells import (
    apply_multi_project,
    apply_single_project,
)
from app.modules.accrual.services.importer.drift import detect_drift
from app.modules.accrual.services.importer.matcher import (
    index_projects,
    resolve_candidates,
)
from app.modules.accrual.services.importer.parser import (
    SpreadsheetRow,
    _normalize_code,
)
from app.modules.accrual.services.importer.periods import bootstrap_periods
from app.modules.accrual.services.importer.snapshot import snapshot_excel_rows

logger = structlog.get_logger()


async def _load_aliases(db: AsyncSession) -> dict[str, list[UUID]]:
    """Return {excel_code (normalized): [project_id, ...]} from accrual_aliases."""
    result = await db.execute(select(AccrualAliasDB))
    by_code: dict[str, list[UUID]] = defaultdict(list)
    for alias in result.scalars().all():
        norm = _normalize_code(alias.excel_code)
        if norm:
            by_code[norm].append(alias.project_id)
    return by_code


def _resolve_via_aliases(
    row: SpreadsheetRow,
    aliases: dict[str, list[UUID]],
    projects_by_id: dict[UUID, object],
) -> list:
    """Return projects mapped by alias for this row, or empty list."""
    norm = _normalize_code(row.code)
    if not norm or norm not in aliases:
        return []
    return [projects_by_id[pid] for pid in aliases[norm] if pid in projects_by_id]


async def _apply_team_budget_fallback(
    db: AsyncSession,
    projects_without_excel: list,
) -> int:
    """Phase 3.5: redistribute team budget across full range for projects with
    no Excel match but with budget+dates set. Cells get ``source='team_budget'``.

    Skips projects that already have any non-frozen cell (would imply a prior
    Excel match that's now gone — leave as-is until human review via drift).
    """
    cells_written = 0
    for project in projects_without_excel:
        if project.budget is None or not project.start_date or not project.end_date:
            continue
        existing = (
            await db.execute(
                select(ProjectAccrualCellDB.id)
                .where(ProjectAccrualCellDB.project_id == project.id)
                .limit(1)
            )
        ).first()
        if existing:
            continue
        written = await cell_service.redistribute_for_project(
            db,
            project_id=project.id,
            full_range=True,
            source=CellSource.TEAM_BUDGET,
        )
        cells_written += written
    return cells_written


async def _load_eligible_projects(db: AsyncSession) -> list:
    result = await db.execute(
        select(ProjectDB).where(
            ProjectDB.status.in_(["proposal", "live", "finished"]),
            ProjectDB.is_billable.is_(True),
        )
    )
    projects = list(result.scalars().all())
    return [p for p in projects if p.start_date and p.end_date]


async def run_pipeline(
    db: AsyncSession,
    *,
    rows: list[SpreadsheetRow],
    source_path: str | None = None,
    triggered_by: UUID | None = None,
    today: date | None = None,
) -> dict:
    """Execute the 5-phase pipeline. Returns a per-phase report dict.

    Caller owns the transaction. The pipeline assumes it runs inside one
    (typically ``async with db.begin(): ...``) so on exception nothing is
    persisted.
    """
    today = today or date.today()
    run = AccrualImportRunDB(
        id=uuid4(),
        source_path=source_path,
        triggered_by=triggered_by,
    )
    db.add(run)
    await db.flush()
    logger.info("accrual_import_started", run_id=str(run.id), rows=len(rows))

    # Phase 1: Snapshot.
    rows_persisted = await snapshot_excel_rows(db, import_run_id=run.id, rows=rows)

    # Bootstrap periods (covers Jan-1 of each year up to current_year).
    await bootstrap_periods(db, rows)

    # Phase 2 + 3: Resolve + Render.
    eligible = await _load_eligible_projects(db)
    projects_by_id = {p.id: p for p in eligible}
    by_full, by_prefix = index_projects(eligible)
    aliases = await _load_aliases(db)

    report: dict = {
        "rows_parsed": len(rows),
        "rows_persisted": rows_persisted,
        # ``matched`` and ``matched_projects`` are kept as parallel aliases —
        # ``matched`` is the legacy key used by external callers and tests.
        "matched": 0,
        "matched_projects": 0,
        "original_budget_set": 0,
        "overrides_imported": 0,
        "unmatched": [],
        "date_mismatches": [],
        "multi_project_groups": [],
    }
    resolutions: list[tuple[object, list[SpreadsheetRow]]] = []
    matched_project_ids: set[UUID] = set()
    rows_by_project: dict[UUID, list[SpreadsheetRow]] = defaultdict(list)
    unmatched_codes: list[str] = []

    for row in rows:
        if not row.code:
            continue
        # Alias takes precedence; fall back to code-based matching.
        candidates = _resolve_via_aliases(row, aliases, projects_by_id) or resolve_candidates(
            row, by_full, by_prefix
        )
        if not candidates:
            report["unmatched"].append({"code": row.code, "name": row.name, "type": row.type})
            unmatched_codes.append(row.code)
            continue

        report["matched_projects"] += len(candidates)
        report["matched"] += len(candidates)
        if len(candidates) == 1:
            await apply_single_project(db, row=row, project=candidates[0], report=report)
            matched_project_ids.add(candidates[0].id)
            rows_by_project[candidates[0].id].append(row)
        else:
            await apply_multi_project(db, row=row, projects=candidates, report=report)
            for p in candidates:
                matched_project_ids.add(p.id)
                rows_by_project[p.id].append(row)

    for project_id, project_rows in rows_by_project.items():
        resolutions.append((projects_by_id[project_id], project_rows))

    # Phase 3.5: Team-budget fallback for unmatched projects with budget+dates.
    projects_without_excel = [p for p in eligible if p.id not in matched_project_ids]
    fallback_written = await _apply_team_budget_fallback(db, projects_without_excel)
    report["team_budget_fallback_cells"] = fallback_written

    # Phase 4: Drift detection.
    drift_count = await detect_drift(
        db,
        import_run_id=run.id,
        excel_resolutions=resolutions,
        projects_without_excel=projects_without_excel,
        unmatched_excel_codes=unmatched_codes,
        today=today,
    )
    report["drift_findings_count"] = drift_count

    # Phase 5: Stamp the import_run with totals.
    from datetime import UTC, datetime

    run.completed_at = datetime.now(UTC)
    run.rows_parsed = len(rows)
    run.rows_mapped = len(matched_project_ids)
    run.rows_unmatched = len(unmatched_codes)
    run.drift_findings_count = drift_count
    run.raw_report = _serialize_report(report)
    await db.flush()
    logger.info(
        "accrual_import_completed",
        run_id=str(run.id),
        rows_persisted=rows_persisted,
        matched_projects=len(matched_project_ids),
        unmatched=len(unmatched_codes),
        drift_findings=drift_count,
        fallback_cells=fallback_written,
    )

    report["import_run_id"] = str(run.id)
    return report


def _serialize_report(report: dict) -> dict:
    """Convert non-JSON values (Decimal, UUID) to strings so the dict can be
    stored as JSONB. Recursive.
    """

    def conv(v: object) -> object:
        if isinstance(v, Decimal):
            return str(v)
        if isinstance(v, UUID):
            return str(v)
        if isinstance(v, dict):
            return {k: conv(val) for k, val in v.items()}
        if isinstance(v, (list, tuple)):
            return [conv(item) for item in v]
        return v

    return {k: conv(v) for k, v in report.items() if k != "import_run_id"}


async def import_projects(db: AsyncSession, rows: list[SpreadsheetRow]) -> dict:
    """Legacy entry-point — thin wrapper around ``run_pipeline``.

    Existing scripts and tests call ``import_projects(db, rows)`` and inspect
    the report keys ``matched``, ``unmatched``, ``date_mismatches``,
    ``multi_project_groups``, ``original_budget_set``, ``overrides_imported``.
    The new pipeline returns the same keys plus extras (drift findings, fallback
    cells, import_run_id).
    """
    return await run_pipeline(db, rows=rows)
