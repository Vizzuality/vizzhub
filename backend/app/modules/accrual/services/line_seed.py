"""One-time seed builder: accrual_excel_rows → accrual lines + verbatim cells.

This is the slice-3 seed that replaces the legacy importer render. It is a
**one-time** operation (the Excel is abandoned afterwards — VizzHub becomes the
source of truth), so it does a clean rebuild rather than an incremental merge.

Design contract (see docs/accrual_lines_design.md):
- Every Excel row becomes a **line**. Cells are rendered **verbatim** from the
  row's ``monthly_cells`` — no ``cell_in_range`` gating (the legacy 147-cell drop
  is gone) and no remainder redistribution (so the grid matches the CEO's Excel
  cell-for-cell). ``value_eur`` is the row total; any gap to Σcells is a real,
  visible "not fully scheduled" divergence.
- A line links to 0..N projects. Resolution precedence: explicit by-id overlay
  (triage decisions for empty/duplicate codes) > persisted aliases > code match.
  Rows in ``unlinked_codes`` become unlinked lines (real income, no project).
  Rows in ``excluded_codes`` are dropped (genuine errors/duplicates).
- Projects with budget+dates and no Excel line get a ``team_budget`` line
  (uniform redistribution across the contract) — same intent as the old fallback.
- Period freezes are re-derived: cells before the open period's start are frozen.

The client-code-specific decision overlay lives in a gitignored runner; this
module is generic and carries no client data.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.services.exchange_rate_service import currency_to_code
from app.modules.accrual.models.accrual_alias import AccrualAliasDB
from app.modules.accrual.models.accrual_excel_row import AccrualExcelRowDB
from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from app.modules.accrual.models.project_accrual_cell import CellSource, ProjectAccrualCellDB
from app.modules.accrual.services import period_service
from app.modules.accrual.services.importer.matcher import index_projects, resolve_candidates
from app.modules.accrual.services.importer.parser import _normalize_code

logger = structlog.get_logger()


def _eom_first(year: int, month: int) -> date:
    """First-of-month date for a (year, month) cell coordinate."""
    return date(year, month, 1)


def _resolve_currency(
    row_currency: str | None,
    projects: list[ProjectDB],
    rate: Decimal | None,
) -> str | None:
    """ISO currency for a line. The Excel rows carry no currency code (only a
    conversion rate), so derive it from the linked project's currency; for
    unlinked lines a rate of 1 means the figure is already EUR.
    """
    if row_currency:
        return currency_to_code(row_currency)
    for p in projects:
        if p.currency:
            return currency_to_code(p.currency)
    if rate is None or rate == Decimal("1"):
        return "EUR"
    return None


def _union_window(
    monthly: list[dict],
    projects: list[ProjectDB],
) -> tuple[date | None, date | None]:
    """Window = union(linked contract dates, Excel month span). Nulls ignored."""
    starts: list[date] = []
    ends: list[date] = []
    if monthly:
        ys = [(int(c["year"]), int(c["month"])) for c in monthly]
        starts.append(_eom_first(*min(ys)))
        ends.append(_eom_first(*max(ys)))
    for p in projects:
        if p.start_date:
            starts.append(p.start_date)
        if p.end_date:
            ends.append(p.end_date)
    return (min(starts) if starts else None, max(ends) if ends else None)


def _months_between(start: date, end: date) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return out


async def _load_eligible_projects(db: AsyncSession) -> list[ProjectDB]:
    result = await db.execute(
        select(ProjectDB).where(
            ProjectDB.status.in_(["proposal", "live", "finished"]),
            ProjectDB.is_billable.is_(True),
        )
    )
    return [p for p in result.scalars().all() if p.start_date and p.end_date]


async def _load_aliases(db: AsyncSession) -> dict[str, list[UUID]]:
    result = await db.execute(select(AccrualAliasDB))
    by_code: dict[str, list[UUID]] = defaultdict(list)
    for a in result.scalars().all():
        norm = _normalize_code(a.excel_code)
        if norm:
            by_code[norm].append(a.project_id)
    return by_code


def _resolve_projects(
    norm: str,
    excel_code: str,
    *,
    unlinked: set[str],
    links_by_id: dict[str, list[UUID]],
    aliases: dict[str, list[UUID]],
    projects_by_id: dict[UUID, ProjectDB],
    by_full: dict,
    by_prefix: dict,
) -> list[ProjectDB]:
    """Resolve a row's linked projects. Precedence: unlinked overlay → explicit
    by-id → persisted aliases → code match. Returns [] for unlinked lines."""
    if norm in unlinked:
        return []
    if norm in links_by_id:
        ids = links_by_id[norm]
    elif norm in aliases:
        ids = aliases[norm]
    else:
        return resolve_candidates(SimpleNamespace(code=excel_code), by_full, by_prefix)
    return [projects_by_id[p] for p in ids if p in projects_by_id]


async def _add_excel_line(
    db: AsyncSession,
    row: AccrualExcelRowDB,
    projects: list[ProjectDB],
    *,
    import_run_id: UUID,
    report: dict,
) -> set[UUID]:
    """Create one Excel line with verbatim cells + project links. Returns the
    project ids it linked (so team-budget fallback can skip them)."""
    monthly = list(row.monthly_cells or [])
    w_start, w_end = _union_window(monthly, projects)
    line = AccrualLineDB(
        id=uuid4(),
        name=row.name,
        source=LineSource.EXCEL.value,
        excel_code=row.excel_code,
        import_run_id=import_run_id,
        value_orig=row.value_orig,
        currency=_resolve_currency(row.currency, projects, row.rate),
        rate=row.rate,
        value_eur=row.value_eur or Decimal("0"),
        window_start=w_start,
        window_end=w_end,
    )
    db.add(line)
    await db.flush()

    linked: set[UUID] = set()
    for p in projects:
        db.add(AccrualLineProjectDB(line_id=line.id, project_id=p.id))
        linked.add(p.id)
        report["links"] += 1

    single_pid = projects[0].id if len(projects) == 1 else None
    for c in monthly:
        db.add(
            ProjectAccrualCellDB(
                line_id=line.id,
                project_id=single_pid,
                year=int(c["year"]),
                month=int(c["month"]),
                amount=Decimal(str(c["eur_amount"])),
                is_manual_override=False,
                is_frozen=False,
                source=CellSource.EXCEL.value,
            )
        )
        report["excel_cells"] += 1

    report["lines_unlinked" if not projects else "lines_excel"] += 1
    return linked


async def _add_team_budget_line(db: AsyncSession, project: ProjectDB, *, report: dict) -> None:
    """Uniform-redistribution fallback line for an eligible project with no Excel line."""
    months = _months_between(project.start_date, project.end_date)
    if not months:
        return
    per_month = (Decimal(project.budget) / Decimal(len(months))).quantize(Decimal("0.01"))
    line = AccrualLineDB(
        id=uuid4(),
        name=project.name,
        source=LineSource.TEAM_BUDGET.value,
        excel_code=project.code,
        value_orig=project.original_budget,
        currency=currency_to_code(project.currency) if project.currency else None,
        value_eur=Decimal(project.budget),
        window_start=project.start_date,
        window_end=project.end_date,
    )
    db.add(line)
    await db.flush()
    db.add(AccrualLineProjectDB(line_id=line.id, project_id=project.id))
    report["links"] += 1
    for y, m in months:
        db.add(
            ProjectAccrualCellDB(
                line_id=line.id,
                project_id=project.id,
                year=y,
                month=m,
                amount=per_month,
                is_manual_override=False,
                is_frozen=False,
                source=CellSource.TEAM_BUDGET.value,
            )
        )
        report["team_budget_cells"] += 1
    report["lines_team_budget"] += 1


async def seed_lines_from_excel_rows(
    db: AsyncSession,
    *,
    import_run_id: UUID,
    links_by_id: dict[str, list[UUID]] | None = None,
    unlinked_codes: set[str] | None = None,
    excluded_codes: set[str] | None = None,
) -> dict:
    """Clean-rebuild accrual lines + cells from a run's Excel rows. Returns a report.

    Caller owns the transaction. Destructive: wipes existing lines/links/cells.
    """
    links_by_id = {(_normalize_code(k) or k): v for k, v in (links_by_id or {}).items()}
    unlinked = {_normalize_code(c) or c for c in (unlinked_codes or set())}
    excluded = {_normalize_code(c) or c for c in (excluded_codes or set())}

    # Clean slate (one-time rebuild).
    await db.execute(delete(ProjectAccrualCellDB))
    await db.execute(delete(AccrualLineProjectDB))
    await db.execute(delete(AccrualLineDB))
    await db.flush()

    eligible = await _load_eligible_projects(db)
    projects_by_id = {p.id: p for p in eligible}
    by_full, by_prefix = index_projects(eligible)
    aliases = await _load_aliases(db)

    rows_result = await db.execute(
        select(AccrualExcelRowDB)
        .where(AccrualExcelRowDB.import_run_id == import_run_id)
        .order_by(AccrualExcelRowDB.import_run_position)
    )
    rows = list(rows_result.scalars().all())

    report = {
        "lines_excel": 0,
        "lines_unlinked": 0,
        "lines_team_budget": 0,
        "excluded": 0,
        "excel_cells": 0,
        "team_budget_cells": 0,
        "links": 0,
    }
    linked_project_ids: set[UUID] = set()

    for row in rows:
        norm = _normalize_code(row.excel_code) or row.excel_code
        if norm in excluded:
            report["excluded"] += 1
            continue
        projects = _resolve_projects(
            norm,
            row.excel_code,
            unlinked=unlinked,
            links_by_id=links_by_id,
            aliases=aliases,
            projects_by_id=projects_by_id,
            by_full=by_full,
            by_prefix=by_prefix,
        )
        linked_project_ids |= await _add_excel_line(
            db, row, projects, import_run_id=import_run_id, report=report
        )

    # Team-budget lines for eligible projects with budget+dates and no Excel line.
    for p in eligible:
        if p.id not in linked_project_ids and p.budget is not None:
            await _add_team_budget_line(db, p, report=report)

    await db.flush()
    await _refreeze_closed_cells(db)

    logger.info("accrual_line_seed_completed", **report)
    return report


async def _refreeze_closed_cells(db: AsyncSession) -> int:
    """Freeze cells whose month falls before the open period's start. Idempotent.

    The freeze is a mechanical consequence of period boundaries (closed periods
    lock their months); the seed re-derives it rather than preserving the prior
    per-cell flags, which were keyed to the now-replaced cells.
    """
    open_period = await period_service.get_current_period(db)
    if open_period is None:
        return 0
    cutoff = open_period.start_date
    cells = (
        (
            await db.execute(
                select(ProjectAccrualCellDB).where(ProjectAccrualCellDB.is_frozen.is_(False))
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    frozen = 0
    for cell in cells:
        if _eom_first(cell.year, cell.month) < cutoff:
            cell.is_frozen = True
            cell.frozen_at = now
            cell.frozen_eur_amount = cell.amount
            frozen += 1
    if frozen:
        await db.flush()
    return frozen
