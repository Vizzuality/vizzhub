"""Widget export endpoints for ISO Docs."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select, tuple_

from app.core.api.deps import CurrentUser, DBSession, ScoringConfigDep, limiter
from app.core.services.export_helpers import XLSX_MEDIA_TYPE
from app.modules.iso_docs.api.deps import check_user_access
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.services.kpi_export_service import KpiExportService
from app.modules.scorecard.models.global_metrics import GlobalMetricsDB, GlobalMetricsRecord

logger = structlog.get_logger()
router = APIRouter()


@router.get("/widgets/{node_id}/export")
@limiter.limit("10/minute")
async def export_kpi_widget(
    request: Request,
    node_id: UUID,
    user: CurrentUser,
    db: DBSession,
    config: ScoringConfigDep,
    year: Annotated[int, Query(ge=2020, le=2100)] = 2025,
    format: Annotated[str, Query()] = "xlsx",
) -> Response:
    """Export KPI Dashboard widget data as XLSX.

    ISO cycle for year Y runs from March Y to February Y+1.
    Returns a two-sheet workbook: Global Scorecard + KPIs manuales.
    """
    await check_user_access(db, node_id, user)

    node_result = await db.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.id == node_id)
    )
    node = node_result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.type != "widget":
        raise HTTPException(status_code=400, detail="Node is not a widget")

    start_year, start_month = year, 3
    end_year, end_month = year + 1, 2

    periods = [
        (y, m)
        for y, m in _iter_periods(start_year, start_month, end_year, end_month)
    ]

    global_rows_result = await db.execute(
        select(GlobalMetricsDB).where(
            tuple_(GlobalMetricsDB.period_year, GlobalMetricsDB.period_month).in_(periods)
        )
    )
    global_by_period: dict[tuple[int, int], GlobalMetricsRecord | None] = dict.fromkeys(periods)
    for row in global_rows_result.scalars().all():
        key = (row.period_year, row.period_month)
        if key in global_by_period:
            global_by_period[key] = GlobalMetricsRecord.from_db(row)

    registry_rows_result = await db.execute(
        select(RegistryRowDB)
        .where(RegistryRowDB.node_id == node_id)
        .where(RegistryRowDB.year == year)
        .order_by(RegistryRowDB.row_index)
    )
    manual_rows = registry_rows_result.scalars().all()

    service = KpiExportService(config)
    xlsx_bytes = service.build_xlsx(
        global_by_period=global_by_period,
        manual_rows=manual_rows,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )

    filename = f"kpi_dashboard_{year}.xlsx"
    logger.info(
        "kpi_widget_exported",
        node_id=str(node_id),
        year=year,
        manual_row_count=len(manual_rows),
        user_email=user.email,
    )

    return Response(
        content=xlsx_bytes.read(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _iter_periods(
    start_year: int, start_month: int, end_year: int, end_month: int
):
    """Yield (year, month) tuples for the given inclusive range."""
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        yield year, month
        month += 1
        if month > 12:
            month = 1
            year += 1
