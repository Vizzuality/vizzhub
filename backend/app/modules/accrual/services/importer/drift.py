"""Phase 4: Detect divergences between tracker state and Excel snapshot.

Compares each project's dates / status / budget vs the Excel rows that resolved
to it, and inserts ``accrual_drift_findings`` for human review.

Kinds emitted here:
- date_extend: Excel covers a later end_date than the tracker project.
- date_shrink: Excel ends earlier than the tracker project.
- status_stale: tracker says 'live' but end_date is in the past.
- missing_tracker: Excel row resolved to no tracker project.
- value_drift: Σ Excel cells diverges from tracker budget beyond threshold.

NOTE: ``missing_excel`` is NOT emitted as a finding. Projects without an Excel
row are handled silently by Phase 3.5 (team-budget uniform fallback) — that's
the normal accrual path for simple/non-forecasted projects, not a divergence.
The ``DriftKind.MISSING_EXCEL`` value is retained for back-compat with rows
already persisted, but no new findings of that kind are written.

The pipeline calls these helpers AFTER cells have been rendered. Drift findings
are additive — older unresolved findings are not cleared (they may have been
manually acknowledged with notes).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_drift_finding import AccrualDriftFindingDB, DriftKind
from app.modules.accrual.services.importer.parser import SpreadsheetRow

# Threshold (relative): cells must diverge from team budget by at least this
# fraction to raise a value_drift finding. Smaller diffs are noise (rounding,
# proportional split rounding, etc.).
_VALUE_DRIFT_THRESHOLD = Decimal("0.05")


def _add(
    db: AsyncSession,
    *,
    import_run_id: UUID,
    kind: DriftKind,
    project_id: UUID | None,
    excel_code: str | None,
    payload: dict,
) -> None:
    db.add(
        AccrualDriftFindingDB(
            import_run_id=import_run_id,
            kind=kind.value,
            project_id=project_id,
            excel_code=excel_code,
            payload=payload,
        )
    )


async def detect_drift(
    db: AsyncSession,
    *,
    import_run_id: UUID,
    excel_resolutions: list[tuple[object, list[SpreadsheetRow]]],
    projects_without_excel: list,
    unmatched_excel_codes: list[str],
    today: date | None = None,
) -> int:
    """Emit drift findings for the given resolutions.

    Inputs:
    - ``excel_resolutions``: list of (project, [excel_rows]) tuples — rows that
      resolved to this project.
    - ``projects_without_excel``: tracker projects with budget+dates and no Excel match.
    - ``unmatched_excel_codes``: Excel codes whose rows resolved to no tracker project.

    Returns the total count of findings emitted.
    """
    today = today or date.today()
    count = 0

    for project, rows in excel_resolutions:
        project_id = project.id
        excel_end = max(
            (r.end_date for r in rows if r.end_date),
            default=None,
        )
        excel_start = min(
            (r.start_date for r in rows if r.start_date),
            default=None,
        )
        excel_sum = sum((r.value_eur or Decimal("0") for r in rows), Decimal("0"))
        excel_code = rows[0].code or ""

        if excel_end and project.end_date and excel_end > project.end_date:
            _add(
                db,
                import_run_id=import_run_id,
                kind=DriftKind.DATE_EXTEND,
                project_id=project_id,
                excel_code=excel_code,
                payload={
                    "tracker_end": str(project.end_date),
                    "excel_end": str(excel_end),
                    "delta_months": (
                        (excel_end.year - project.end_date.year) * 12
                        + (excel_end.month - project.end_date.month)
                    ),
                },
            )
            count += 1

        if excel_end and project.end_date and excel_end < project.end_date:
            _add(
                db,
                import_run_id=import_run_id,
                kind=DriftKind.DATE_SHRINK,
                project_id=project_id,
                excel_code=excel_code,
                payload={
                    "tracker_end": str(project.end_date),
                    "excel_end": str(excel_end),
                },
            )
            count += 1

        if project.status == "live" and project.end_date and project.end_date < today:
            _add(
                db,
                import_run_id=import_run_id,
                kind=DriftKind.STATUS_STALE,
                project_id=project_id,
                excel_code=excel_code,
                payload={
                    "tracker_end": str(project.end_date),
                    "excel_end": str(excel_end) if excel_end else None,
                    "today": str(today),
                },
            )
            count += 1

        if project.budget and excel_sum > 0:
            budget = Decimal(project.budget)
            diff = excel_sum - budget
            rel = (diff / budget).copy_abs()
            if rel > _VALUE_DRIFT_THRESHOLD:
                _add(
                    db,
                    import_run_id=import_run_id,
                    kind=DriftKind.VALUE_DRIFT,
                    project_id=project_id,
                    excel_code=excel_code,
                    payload={
                        "tracker_budget_eur": str(budget),
                        "excel_sum_eur": str(excel_sum),
                        "diff_eur": str(diff),
                        "diff_pct": str((rel * 100).quantize(Decimal("0.01"))),
                    },
                )
                count += 1

        # Silence unused locals when no extend/shrink fired.
        _ = excel_start

    # Projects without an Excel row are NOT flagged. Phase 3.5 already applies
    # a uniform team-budget fallback for them, which is the correct accrual
    # baseline when there's no forecast data — not a divergence to review.
    _ = projects_without_excel

    for code in unmatched_excel_codes:
        _add(
            db,
            import_run_id=import_run_id,
            kind=DriftKind.MISSING_TRACKER,
            project_id=None,
            excel_code=code,
            payload={},
        )
        count += 1

    await db.flush()
    return count
