"""Widget export endpoints for ISO Docs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from typing import Annotated
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select, tuple_

from app.core.api.deps import CurrentUser, DBSession, ScoringConfigDep, limiter
from app.core.services.export_helpers import XLSX_MEDIA_TYPE
from app.modules.iso_docs.api.deps import IsoDocsEditor, check_user_access
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.services.kpi_export_service import KpiExportService, generate_iso_periods
from app.modules.scorecard.models.global_metrics import GlobalMetricsDB, GlobalMetricsRecord

logger = structlog.get_logger()
router = APIRouter()

DRIVE_API = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


@router.get(
    "/widgets/{node_id}/export",
    responses={404: {"description": "Widget node not found"}},
)
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
    if node is None or node.type != "widget":
        raise HTTPException(status_code=404, detail="Widget node not found")

    xlsx_buf = await _build_widget_xlsx(db, node_id, year, config)

    filename = f"kpi_dashboard_{year}.xlsx"
    logger.info("kpi_widget_exported", node_id=str(node_id), year=year)

    return Response(
        content=xlsx_buf.read(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _build_widget_xlsx(db, node_id: UUID, year: int, config) -> BytesIO:
    """Build XLSX for KPI widget — shared by download and Drive export."""
    start_year, start_month = year, 3
    end_year, end_month = year + 1, 2
    periods = generate_iso_periods(start_year, start_month, end_year, end_month)

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

    return KpiExportService(config).build_xlsx(
        global_by_period=global_by_period,
        manual_rows=manual_rows,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
    )


@router.post(
    "/widgets/{node_id}/export-drive",
    responses={
        404: {"description": "Widget node not found"},
        400: {"description": "Google Drive not connected"},
    },
)
@limiter.limit("10/minute")
async def export_kpi_widget_to_drive(
    request: Request,
    node_id: UUID,
    user: IsoDocsEditor,
    db: DBSession,
    config: ScoringConfigDep,
    year: Annotated[int, Query(ge=2020, le=2100)] = 2025,
) -> dict:
    """Export KPI Dashboard widget to Google Drive as a spreadsheet."""
    from app.modules.iso_docs.models.drive_mapping import IsoDocDriveMappingDB
    from app.modules.iso_docs.services.google_drive_oauth import GoogleDriveOAuth

    access_token = await GoogleDriveOAuth.get_valid_token(db)
    if not access_token:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    node_result = await db.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.id == node_id)
    )
    node = node_result.scalar_one_or_none()
    if node is None or node.type != "widget":
        raise HTTPException(status_code=404, detail="Widget node not found")

    xlsx_buf = await _build_widget_xlsx(db, node_id, year, config)
    file_name = f"{node.title} ({year}–{year + 1})"

    async with httpx.AsyncClient(timeout=DRIVE_TIMEOUT) as http:
        auth_header = {"Authorization": f"Bearer {access_token}"}

        from app.modules.iso_docs.api.registry_rows import _resolve_drive_parent
        parent_drive_id = await _resolve_drive_parent(db, node, http, auth_header)

        existing_mapping = await db.execute(
            select(IsoDocDriveMappingDB).where(IsoDocDriveMappingDB.node_id == node.id)
        )
        existing = existing_mapping.scalar_one_or_none()
        existing_drive_id = existing.drive_file_id if existing else None

        if existing_drive_id:
            check = await http.get(
                f"{DRIVE_API}/{existing_drive_id}",
                headers=auth_header,
                params={"fields": "id,trashed", "supportsAllDrives": "true"},
            )
            if check.status_code == 200 and not check.json().get("trashed"):
                await http.patch(
                    f"{DRIVE_API}/{existing_drive_id}",
                    json={"name": file_name},
                    headers=auth_header,
                    params={"supportsAllDrives": "true"},
                )
                await http.patch(
                    f"{DRIVE_UPLOAD_API}/{existing_drive_id}?uploadType=media",
                    content=xlsx_buf.read(),
                    headers={**auth_header, "Content-Type": XLSX_MEDIA_TYPE},
                    params={"supportsAllDrives": "true"},
                )
                drive_file_id = existing_drive_id
            else:
                existing_drive_id = None

        if not existing_drive_id:
            drive_meta = {
                "name": file_name,
                "parents": [parent_drive_id],
                "mimeType": "application/vnd.google-apps.spreadsheet",
            }
            resp = await http.post(
                f"{DRIVE_UPLOAD_API}?uploadType=multipart",
                headers=auth_header,
                files={
                    "metadata": (None, json.dumps(drive_meta).encode(), "application/json"),
                    "file": (None, xlsx_buf.read(), XLSX_MEDIA_TYPE),
                },
                params={"fields": "id", "supportsAllDrives": "true"},
            )
            resp.raise_for_status()
            drive_file_id = resp.json()["id"]

    now = datetime.now(timezone.utc)
    if existing:
        existing.drive_file_id = drive_file_id
        existing.last_exported_at = now
    else:
        db.add(IsoDocDriveMappingDB(
            node_id=node.id,
            drive_file_id=drive_file_id,
            drive_file_type="spreadsheet",
            last_exported_at=now,
        ))
    await db.flush()

    logger.info("kpi_widget_exported_to_drive", node_id=str(node_id), drive_file_id=drive_file_id)
    return {"drive_file_id": drive_file_id}
