"""Phase 1: Persist parsed Excel rows to ``accrual_excel_rows`` as a snapshot.

Each importer run gets its own ``accrual_import_run`` (created by the
pipeline) and all parsed rows are inserted with ``import_run_id`` set to it,
so historical snapshots are preserved across runs.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_excel_row import AccrualExcelRowDB
from app.modules.accrual.services.importer.parser import SpreadsheetRow


async def snapshot_excel_rows(
    db: AsyncSession,
    *,
    import_run_id: UUID,
    rows: list[SpreadsheetRow],
) -> int:
    """Insert every parsed Excel row into ``accrual_excel_rows``.

    Returns the count of rows persisted. ``monthly_cells`` is stored as a
    JSONB list ``[{"year": Y, "month": M, "eur_amount": "123.45"}, ...]`` for
    later rendering and drift checks. No deduplication / consolidation here —
    that happens at resolve/render time via the alias table.
    """
    inserted = 0
    for position, row in enumerate(rows):
        monthly_cells = [
            {"year": y, "month": m, "eur_amount": str(amount)}
            for (y, m), amount in sorted(row.monthly.items())
        ]
        db.add(
            AccrualExcelRowDB(
                import_run_id=import_run_id,
                import_run_position=position,
                excel_code=row.code or "",
                name=row.name,
                pm_name=row.pm,
                client=None,
                value_orig=row.value or None,
                currency=None,
                rate=row.rate or None,
                value_eur=row.value_eur or 0,
                start_date=row.start_date,
                end_date=row.end_date,
                months=row.duration,
                monthly_cells=monthly_cells,
            )
        )
        inserted += 1
    await db.flush()
    return inserted
