"""Registry row CRUD + reorder + export endpoints."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from io import BytesIO, StringIO
from typing import Annotated
from uuid import UUID

import httpx
import openpyxl
import structlog
from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from openpyxl.utils import get_column_letter
from sqlalchemy import delete as sql_delete, select

from app.core.api.deps import CurrentUser, DBSession
from app.modules.iso_docs.api.deps import IsoDocsEditor
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.iso_docs.schemas.registry import (
    RegistryRowCreate,
    RegistryRowReorder,
    RegistryRowResponse,
    RegistryRowUpdate,
)
from app.modules.iso_docs.services.drive_export_service import (
    DRIVE_API,
    DRIVE_TIMEOUT,
    DRIVE_UPLOAD_API,
)
from app.modules.iso_docs.services.registry_service import (
    get_next_row_index,
    validate_row_data,
)

logger = structlog.get_logger()

XLSX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

router = APIRouter()


async def _get_registry_node(db, node_id: UUID) -> IsoDocNodeDB:
    result = await db.execute(
        select(IsoDocNodeDB).where(
            IsoDocNodeDB.id == node_id, IsoDocNodeDB.type == "registry"
        )
    )
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Registry node not found")
    return node


async def _get_registry_type(db, type_id: UUID) -> RegistryTypeDB:
    result = await db.execute(
        select(RegistryTypeDB).where(RegistryTypeDB.id == type_id)
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=404, detail="Registry type not found")
    return rt


async def _fetch_rows(db, node_id: UUID, year: int | None = None) -> list:
    """Fetch ordered rows for a registry node, optionally filtered by year."""
    query = (
        select(RegistryRowDB)
        .where(RegistryRowDB.node_id == node_id)
        .order_by(RegistryRowDB.row_index)
    )
    if year is not None:
        query = query.where(RegistryRowDB.year == year)
    result = await db.execute(query)
    return list(result.scalars())


@router.get("/registries/{node_id}/rows")
async def list_rows(
    node_id: UUID,
    db: DBSession,
    user: CurrentUser,
    year: Annotated[int | None, Query()] = None,
) -> list[RegistryRowResponse]:
    node = await _get_registry_node(db, node_id)
    rows = await _fetch_rows(db, node.id, year)
    return [RegistryRowResponse.model_validate(r) for r in rows]


@router.post("/registries/{node_id}/rows", status_code=201)
async def create_row(
    node_id: UUID,
    data: RegistryRowCreate,
    db: DBSession,
    user: IsoDocsEditor,
) -> RegistryRowResponse:
    node = await _get_registry_node(db, node_id)
    rt = await _get_registry_type(db, node.registry_type_id)

    if rt.is_yearly and data.year is None:
        raise HTTPException(status_code=400, detail="Year is required for yearly registries")

    errors = validate_row_data(rt.schema, data.data)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    row_index = await get_next_row_index(db, node.id, data.year)
    row = RegistryRowDB(
        node_id=node.id,
        year=data.year,
        row_index=row_index,
        data=data.data,
        created_by_id=UUID(user.user_id),
        updated_by_id=UUID(user.user_id),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    logger.info("registry_row_created", node_id=str(node_id), row_id=str(row.id))
    return RegistryRowResponse.model_validate(row)


@router.patch(
    "/registries/{node_id}/rows/{row_id}",
    responses={404: {"description": "Row not found"}},
)
async def update_row(
    node_id: UUID,
    row_id: UUID,
    data: RegistryRowUpdate,
    db: DBSession,
    user: IsoDocsEditor,
) -> RegistryRowResponse:
    node = await _get_registry_node(db, node_id)
    rt = await _get_registry_type(db, node.registry_type_id)

    result = await db.execute(
        select(RegistryRowDB).where(
            RegistryRowDB.id == row_id, RegistryRowDB.node_id == node.id
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")

    merged = {**row.data, **data.data}
    errors = validate_row_data(rt.schema, merged)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    row.data = merged
    row.updated_by_id = UUID(user.user_id)
    await db.flush()
    await db.refresh(row)
    logger.info("registry_row_updated", node_id=str(node_id), row_id=str(row_id))
    return RegistryRowResponse.model_validate(row)


@router.delete(
    "/registries/{node_id}/rows/{row_id}",
    responses={404: {"description": "Row not found"}},
)
async def delete_row(
    node_id: UUID,
    row_id: UUID,
    db: DBSession,
    user: IsoDocsEditor,
) -> dict:
    await _get_registry_node(db, node_id)

    result = await db.execute(
        select(RegistryRowDB).where(
            RegistryRowDB.id == row_id, RegistryRowDB.node_id == node_id
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Row not found")

    await db.delete(row)
    await db.flush()
    logger.info("registry_row_deleted", node_id=str(node_id), row_id=str(row_id))
    return {"ok": True}


@router.put("/registries/{node_id}/rows/reorder")
async def reorder_rows(
    node_id: UUID,
    data: RegistryRowReorder,
    db: DBSession,
    user: IsoDocsEditor,
) -> dict:
    await _get_registry_node(db, node_id)

    result = await db.execute(
        select(RegistryRowDB).where(
            RegistryRowDB.id.in_(data.row_ids),
            RegistryRowDB.node_id == node_id,
        )
    )
    rows_by_id = {r.id: r for r in result.scalars()}

    for idx, row_id in enumerate(data.row_ids):
        row = rows_by_id.get(row_id)
        if not row:
            raise HTTPException(status_code=404, detail=f"Row {row_id} not found")
        row.row_index = idx

    await db.flush()
    logger.info("registry_rows_reordered", node_id=str(node_id), count=len(data.row_ids))
    return {"ok": True}


@router.get("/registries/{node_id}/export")
async def export_registry(
    node_id: UUID,
    db: DBSession,
    user: CurrentUser,
    year: Annotated[int | None, Query()] = None,
    format: Annotated[str, Query()] = "xlsx",
) -> StreamingResponse:
    node = await _get_registry_node(db, node_id)
    rt = await _get_registry_type(db, node.registry_type_id)
    rows = await _fetch_rows(db, node.id, year)

    columns = rt.schema
    headers = [col["label"] for col in columns]
    base_name = f"{node.title} ({year})" if year else node.title

    if format == "csv":
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.data.get(col["key"], "") for col in columns])

        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.csv"'},
        )

    xlsx_buf = _build_xlsx(node.title, columns, rows)
    return StreamingResponse(
        xlsx_buf,
        media_type=XLSX_CONTENT_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{base_name}.xlsx"'},
    )


def _coerce_csv_value(raw: str, col_type: str) -> object:
    """Convert a CSV string to the appropriate Python type."""
    if raw == "":
        return None
    if col_type == "number":
        try:
            return int(raw)
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return raw
    if col_type == "boolean":
        return raw.lower() in ("true", "yes", "1")
    return raw


def _parse_csv(text: str, columns: list[dict]) -> list[dict]:
    """Parse CSV text into validated row dicts. Raises HTTPException on errors."""
    label_to_col = {col["label"]: col for col in columns}
    reader = csv.DictReader(StringIO(text))

    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no headers")

    unknown = [h for h in reader.fieldnames if h and h not in label_to_col]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown columns: {', '.join(repr(h) for h in unknown)}. Expected: {', '.join(label_to_col.keys())}",
        )

    parsed_rows: list[dict] = []
    for line_num, csv_row in enumerate(reader, start=2):
        data: dict = {}
        for label, raw in csv_row.items():
            col = label_to_col.get(label)
            if not col:
                continue
            data[col["key"]] = _coerce_csv_value(raw or "", col["type"])

        errors = validate_row_data(columns, data)
        if errors:
            raise HTTPException(
                status_code=400,
                detail=f"Row {line_num}: {'; '.join(errors)}",
            )
        parsed_rows.append(data)
    return parsed_rows


@router.post("/registries/{node_id}/import")
async def import_registry(
    node_id: UUID,
    file: UploadFile,
    db: DBSession,
    user: IsoDocsEditor,
    year: Annotated[int | None, Query()] = None,
) -> dict:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    node = await _get_registry_node(db, node_id)
    rt = await _get_registry_type(db, node.registry_type_id)

    content = await file.read()
    text = content.decode("utf-8-sig")
    parsed_rows = _parse_csv(text, rt.schema)

    await db.execute(
        select(RegistryRowDB)
        .where(RegistryRowDB.node_id == node.id)
        .with_for_update()
    )

    if year is not None:
        await db.execute(
            sql_delete(RegistryRowDB).where(
                RegistryRowDB.node_id == node.id,
                RegistryRowDB.year == year,
            )
        )
    else:
        await db.execute(
            sql_delete(RegistryRowDB).where(RegistryRowDB.node_id == node.id)
        )

    for idx, data in enumerate(parsed_rows):
        db.add(
            RegistryRowDB(
                node_id=node.id,
                year=year,
                row_index=idx,
                data=data,
                created_by_id=UUID(user.user_id),
                updated_by_id=UUID(user.user_id),
            )
        )

    await db.flush()
    logger.info(
        "registry_csv_imported",
        node_id=str(node_id),
        rows_imported=len(parsed_rows),
        year=year,
    )
    return {"imported": len(parsed_rows)}


def _build_xlsx(node_title: str, columns: list[dict], rows: list) -> BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = node_title[:31]
    headers = [col["label"] for col in columns]
    ws.append(headers)
    for row in rows:
        ws.append([row.data.get(col["key"], "") for col in columns])

    for col_idx, header in enumerate(headers, 1):
        max_len = len(str(header))
        for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
            val = row[0].value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 3, 50)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


async def _resolve_drive_parent(
    db,
    node: IsoDocNodeDB,
    http: httpx.AsyncClient,
    auth_header: dict[str, str],
) -> str:
    """Walk up ancestors to find a Drive folder, creating missing ones."""
    from app.modules.iso_docs.models.drive_mapping import IsoDocDriveMappingDB
    from app.core.services.integration_token_service import IntegrationTokenService
    from app.modules.iso_docs.services.google_drive_oauth import PROVIDER

    ancestors: list[IsoDocNodeDB] = []
    current = node
    while current.parent_id:
        result = await db.execute(
            select(IsoDocNodeDB).where(IsoDocNodeDB.id == current.parent_id)
        )
        parent = result.scalar_one_or_none()
        if not parent:
            break
        mapping_result = await db.execute(
            select(IsoDocDriveMappingDB).where(
                IsoDocDriveMappingDB.node_id == parent.id
            )
        )
        mapping = mapping_result.scalar_one_or_none()
        if mapping:
            drive_parent_id = mapping.drive_file_id
            break
        ancestors.append(parent)
        current = parent
    else:
        root_folder_id = await IntegrationTokenService.get_setting(
            db, PROVIDER, "root_folder_id"
        )
        if not root_folder_id:
            raise HTTPException(
                status_code=400,
                detail="Google Drive root folder not configured",
            )
        drive_parent_id = root_folder_id

    now = datetime.now(timezone.utc)
    for ancestor in reversed(ancestors):
        body = {
            "name": ancestor.title,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [drive_parent_id],
        }
        resp = await http.post(
            DRIVE_API,
            json=body,
            headers=auth_header,
            params={"fields": "id", "supportsAllDrives": "true"},
        )
        resp.raise_for_status()
        new_folder_id = resp.json()["id"]
        db.add(
            IsoDocDriveMappingDB(
                node_id=ancestor.id,
                drive_file_id=new_folder_id,
                drive_file_type="folder",
                last_exported_at=now,
            )
        )
        await db.flush()
        drive_parent_id = new_folder_id

    return drive_parent_id


@router.post("/registries/{node_id}/export-drive")
async def export_registry_to_drive(
    node_id: UUID,
    db: DBSession,
    user: IsoDocsEditor,
    year: Annotated[int | None, Query()] = None,
) -> dict:
    from app.modules.iso_docs.models.drive_mapping import IsoDocDriveMappingDB
    from app.modules.iso_docs.services.google_drive_oauth import GoogleDriveOAuth

    access_token = await GoogleDriveOAuth.get_valid_token(db)
    if not access_token:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    node = await _get_registry_node(db, node_id)
    rt = await _get_registry_type(db, node.registry_type_id)
    rows = await _fetch_rows(db, node.id, year)

    file_name = f"{node.title} ({year})" if year else node.title
    xlsx_buf = _build_xlsx(node.title, rt.schema, rows)

    async with httpx.AsyncClient(timeout=DRIVE_TIMEOUT) as http:
        auth_header = {"Authorization": f"Bearer {access_token}"}

        parent_drive_id = await _resolve_drive_parent(db, node, http, auth_header)

        existing_mapping = await db.execute(
            select(IsoDocDriveMappingDB).where(
                IsoDocDriveMappingDB.node_id == node.id
            )
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
                    headers={
                        **auth_header,
                        "Content-Type": XLSX_CONTENT_TYPE,
                    },
                    params={"supportsAllDrives": "true"},
                )
                drive_file_id = existing_drive_id
            else:
                existing_drive_id = None

        if not existing_drive_id:
            metadata = {
                "name": file_name,
                "parents": [parent_drive_id],
                "mimeType": "application/vnd.google-apps.spreadsheet",
            }
            resp = await http.post(
                f"{DRIVE_UPLOAD_API}?uploadType=multipart",
                headers=auth_header,
                files={
                    "metadata": (None, json.dumps(metadata).encode(), "application/json"),
                    "file": (
                        None,
                        xlsx_buf.read(),
                        XLSX_CONTENT_TYPE,
                    ),
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
        db.add(
            IsoDocDriveMappingDB(
                node_id=node.id,
                drive_file_id=drive_file_id,
                drive_file_type="spreadsheet",
                last_exported_at=now,
            )
        )
    await db.flush()

    logger.info(
        "registry_exported_to_drive",
        node_id=str(node_id),
        drive_file_id=drive_file_id,
        rows=len(rows),
    )
    return {"drive_file_id": drive_file_id}
