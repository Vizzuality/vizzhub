"""Export ISO Docs tree to Google Drive as folders and Google Docs."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from datetime import datetime, timezone

import httpx
import structlog
from markdown_it import MarkdownIt
from sqlalchemy import delete, select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.job import JobStatus
from app.core.services.integration_token_service import IntegrationTokenService
from app.core.services.job_service import JobService
from app.modules.iso_docs.models.drive_mapping import IsoDocDriveMappingDB
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB
from app.modules.iso_docs.services.google_drive_oauth import GoogleDriveOAuth, PROVIDER

logger = structlog.get_logger()

DRIVE_API = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
ROOT_FOLDER_KEY = "root_folder_id"
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

STATUS_LABELS = {
    "approved": "Approved",
    "draft": "Draft",
    "under_review": "Under Review",
}

_md = MarkdownIt("commonmark", {"html": True}).enable(["table"])

_STYLE = """<style>
body { font-family: Arial, sans-serif; line-height: 1.6; color: #1a1a1a; max-width: 720pt; }
h1 { color: #1a1a1a; }
h2 { font-size: 16pt; color: #333; margin-top: 20pt; margin-bottom: 8pt; }
h3 { font-size: 13pt; color: #444; margin-top: 16pt; margin-bottom: 6pt; }
p { margin: 6pt 0; }
ul, ol { padding-left: 24pt; }
li { margin: 3pt 0; }
table { border-collapse: collapse; margin: 8pt 0; }
th, td { padding: 4pt 8pt; border: 1pt solid #ddd; text-align: left; font-size: 10pt; }
th { background: #f5f5f5; font-weight: bold; }
code { background: #f5f5f5; padding: 1pt 4pt; border-radius: 3pt; font-size: 9pt; }
pre { background: #f8f8f8; padding: 12pt; border-radius: 4pt; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3pt solid #e0e0e0; padding-left: 12pt; color: #555; margin: 8pt 0; }
hr { border: none; border-top: 1pt solid #e0e0e0; margin: 16pt 0; }
a { color: #1a73e8; text-decoration: none; }
</style>"""

_PILL = (
    "display:inline-block;background:#f0f0f0;color:#333;"
    "padding:2pt 8pt;border-radius:3pt;font-size:9pt;font-family:monospace"
)


_RETRYABLE_ERRORS = (httpx.TimeoutException, httpx.ConnectError)
_RETRYABLE_STATUS_CODES = {500, 502, 503, 429}
MAX_RETRIES = 2
RETRY_BACKOFF = 3  # seconds


async def _retry_request(coro_factory, description: str = ""):
    """Retry a Drive API call on transient errors (timeout, 5xx, 429)."""
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = await coro_factory()
            if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                logger.warning(
                    "drive_api_retry",
                    status=resp.status_code,
                    attempt=attempt + 1,
                    description=description,
                )
                await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
                continue
            return resp
        except _RETRYABLE_ERRORS as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                logger.warning(
                    "drive_api_retry",
                    error=str(exc),
                    attempt=attempt + 1,
                    description=description,
                )
                await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
            else:
                raise
    raise last_exc  # type: ignore[misc]


@dataclasses.dataclass
class _WalkContext:
    """Mutable state shared across the recursive tree walk."""

    nodes: list[IsoDocNodeDB]
    mappings: dict[uuid.UUID, str]
    versions_map: dict[uuid.UUID, str]
    metadata_map: dict[uuid.UUID, IsoDocMetadataDB]
    registry_types: dict[uuid.UUID, RegistryTypeDB]
    registry_rows: dict[uuid.UUID, list[RegistryRowDB]]
    total: int
    access_token: str
    exported: int = 0


class DriveExportService:
    """Exports the full ISO Docs tree to Google Drive."""

    _TOKEN_REFRESH_INTERVAL = 300  # seconds between token refresh checks

    async def export_tree(
        self,
        db: AsyncSession,
        job_id: str,
    ) -> dict:
        job_uuid = uuid.UUID(job_id)
        await JobService.update_status(db, job_uuid, JobStatus.RUNNING)
        await JobService.update_progress(db, job_uuid, 0, "Loading documents")

        try:
            access_token = await GoogleDriveOAuth.get_valid_token(db)
            if not access_token:
                raise RuntimeError("Google Drive not connected")
            self._token_refreshed_at = datetime.now(timezone.utc)

            data = await self._load_data(db)
            nodes = data["nodes"]
            versions_map = data["versions_map"]
            metadata_map = data["metadata_map"]
            registry_types = data["registry_types"]
            registry_rows = data["registry_rows"]
            if not nodes:
                await JobService.update_status(
                    db, job_uuid, JobStatus.COMPLETED, result={"exported": 0}
                )
                return {"exported": 0}

            mappings = await self._load_mappings(db)
            root_folder_id = await IntegrationTokenService.get_setting(
                db, PROVIDER, ROOT_FOLDER_KEY
            )
            if not root_folder_id:
                raise RuntimeError(
                    "Root folder not configured. Set a Google Drive folder ID in Integrations."
                )

            tree = sorted(
                [n for n in nodes if n.parent_id is None],
                key=lambda n: n.position,
            )

            ctx = _WalkContext(
                nodes=nodes,
                mappings=mappings,
                versions_map=versions_map,
                metadata_map=metadata_map,
                registry_types=registry_types,
                registry_rows=registry_rows,
                total=len(nodes),
                access_token=access_token,
            )

            async with httpx.AsyncClient(timeout=DRIVE_TIMEOUT) as http:
                await self._walk_children(
                    db, http, ctx, tree, root_folder_id, job_uuid,
                )
                access_token = ctx.access_token

                orphan_count = await self._cleanup_orphans(
                    db, http, ctx.access_token,
                    {n.id for n in nodes}, mappings,
                )

            await JobService.update_progress(db, job_uuid, 100, "Export complete")

            result = {
                "exported": ctx.exported,
                "orphans_removed": orphan_count,
                "root_folder_id": root_folder_id,
            }
            await JobService.update_status(
                db, job_uuid, JobStatus.COMPLETED, result=result
            )
            logger.info(
                "drive_export_completed",
                exported=ctx.exported,
                orphans_removed=orphan_count,
            )
            return result

        except Exception as exc:
            logger.error("drive_export_failed", error=str(exc))
            try:
                await JobService.update_status(
                    db, job_uuid, JobStatus.FAILED,
                    error_message=str(exc)[:1000],
                )
            except Exception:
                logger.error("drive_export_status_save_failed", job_id=job_id)
            raise

    async def _walk_children(
        self,
        db: AsyncSession,
        http: httpx.AsyncClient,
        ctx: _WalkContext,
        children: list[IsoDocNodeDB],
        parent_drive_id: str,
        job_uuid: uuid.UUID,
        parent_title: str | None = None,
    ) -> None:
        for node in children:
            if node.type == "widget":
                ctx.exported += 1
                continue

            ctx.access_token = await self._refresh_if_needed(
                db, ctx.access_token
            )
            existing_drive_id = ctx.mappings.get(node.id)

            if node.type == "registry":
                await self._export_registry_node(
                    db, http, ctx, node, parent_drive_id, existing_drive_id,
                )
            elif node.type == "group":
                await self._export_group_node(
                    db, http, ctx, node, parent_drive_id,
                    existing_drive_id, job_uuid,
                )
            else:
                await self._export_page_node(
                    db, http, ctx, node, parent_drive_id,
                    existing_drive_id, parent_title,
                )

            ctx.exported += 1
            pct = int((ctx.exported / ctx.total) * 90) + 5
            await JobService.update_progress(
                db, job_uuid, pct,
                f"Exported {ctx.exported}/{ctx.total}",
            )

    async def _export_registry_node(
        self,
        db: AsyncSession,
        http: httpx.AsyncClient,
        ctx: _WalkContext,
        node: IsoDocNodeDB,
        parent_drive_id: str,
        existing_drive_id: str | None,
    ) -> None:
        rt = ctx.registry_types.get(node.registry_type_id)
        if not rt:
            return
        rows = ctx.registry_rows.get(node.id, [])
        meta = ctx.metadata_map.get(node.id)
        drive_id = await self._upsert_spreadsheet(
            http, ctx.access_token, node.title,
            rt.schema, rt.is_yearly, rows,
            parent_drive_id, existing_drive_id, meta,
        )
        await self._save_mapping(
            db, node.id, drive_id, "spreadsheet", ctx.mappings,
        )

    async def _export_group_node(
        self,
        db: AsyncSession,
        http: httpx.AsyncClient,
        ctx: _WalkContext,
        node: IsoDocNodeDB,
        parent_drive_id: str,
        existing_drive_id: str | None,
        job_uuid: uuid.UUID,
    ) -> None:
        drive_id = await self._upsert_folder(
            http, ctx.access_token, node.title,
            parent_drive_id, existing_drive_id,
        )
        await self._save_mapping(
            db, node.id, drive_id, "folder", ctx.mappings,
        )
        sub_children = sorted(
            [n for n in ctx.nodes if n.parent_id == node.id],
            key=lambda n: n.title.lower(),
        )
        await self._walk_children(
            db, http, ctx, sub_children, drive_id, job_uuid, node.title,
        )

    async def _export_page_node(
        self,
        db: AsyncSession,
        http: httpx.AsyncClient,
        ctx: _WalkContext,
        node: IsoDocNodeDB,
        parent_drive_id: str,
        existing_drive_id: str | None,
        parent_title: str | None,
    ) -> None:
        content = ctx.versions_map.get(node.id, "")
        meta = ctx.metadata_map.get(node.id)
        html = self._to_html(node.title, content, meta, parent_title)
        drive_id = await self._upsert_doc(
            http, ctx.access_token, node.title, html,
            parent_drive_id, existing_drive_id,
        )
        await self._save_mapping(
            db, node.id, drive_id, "document", ctx.mappings,
        )

    async def _load_data(self, db: AsyncSession) -> dict:
        nodes_result = await db.execute(
            select(IsoDocNodeDB).order_by(IsoDocNodeDB.position)
        )
        nodes = list(nodes_result.scalars().unique().all())

        latest_versions = (
            select(
                IsoDocVersionDB.node_id,
                sa_func.max(IsoDocVersionDB.version).label("max_ver"),
            )
            .group_by(IsoDocVersionDB.node_id)
            .subquery()
        )
        versions_result = await db.execute(
            select(IsoDocVersionDB)
            .join(
                latest_versions,
                (IsoDocVersionDB.node_id == latest_versions.c.node_id)
                & (IsoDocVersionDB.version == latest_versions.c.max_ver),
            )
        )
        versions_map = {v.node_id: v.content for v in versions_result.scalars().all()}

        meta_result = await db.execute(select(IsoDocMetadataDB))
        metadata_map = {m.node_id: m for m in meta_result.scalars().all()}

        rt_result = await db.execute(select(RegistryTypeDB))
        registry_types = {rt.id: rt for rt in rt_result.scalars().all()}

        rows_result = await db.execute(
            select(RegistryRowDB).order_by(RegistryRowDB.row_index)
        )
        registry_rows: dict[uuid.UUID, list[RegistryRowDB]] = {}
        for row in rows_result.scalars().all():
            registry_rows.setdefault(row.node_id, []).append(row)

        return {
            "nodes": nodes,
            "versions_map": versions_map,
            "metadata_map": metadata_map,
            "registry_types": registry_types,
            "registry_rows": registry_rows,
        }

    async def _load_mappings(self, db: AsyncSession) -> dict[uuid.UUID, str]:
        result = await db.execute(select(IsoDocDriveMappingDB))
        return {m.node_id: m.drive_file_id for m in result.scalars().all()}

    async def _refresh_if_needed(
        self, db: AsyncSession, current_token: str
    ) -> str:
        now = datetime.now(timezone.utc)
        elapsed = (now - self._token_refreshed_at).total_seconds()
        if elapsed < self._TOKEN_REFRESH_INTERVAL:
            return current_token
        refreshed = await GoogleDriveOAuth.get_valid_token(db)
        self._token_refreshed_at = now
        return refreshed or current_token

    async def _upsert_folder(
        self,
        http: httpx.AsyncClient,
        token: str,
        name: str,
        parent_drive_id: str,
        existing_drive_id: str | None,
    ) -> str:
        if existing_drive_id and await self._drive_file_exists(http, token, existing_drive_id):
            await self._update_file_metadata(
                http, token, existing_drive_id, name
            )
            return existing_drive_id
        return await self._create_folder(http, token, name, parent_drive_id)

    async def _upsert_doc(
        self,
        http: httpx.AsyncClient,
        token: str,
        title: str,
        html: str,
        parent_drive_id: str,
        existing_drive_id: str | None,
    ) -> str:
        if existing_drive_id and await self._drive_file_exists(http, token, existing_drive_id):
            await self._update_file_metadata(
                http, token, existing_drive_id, title
            )
            await self._update_file_content(http, token, existing_drive_id, html)
            return existing_drive_id
        return await self._create_doc(http, token, title, html, parent_drive_id)

    async def _upsert_spreadsheet(
        self,
        http: httpx.AsyncClient,
        token: str,
        title: str,
        schema: list[dict],
        is_yearly: bool,
        rows: list,
        parent_drive_id: str,
        existing_drive_id: str | None,
        metadata=None,
    ) -> str:
        from app.modules.iso_docs.api.registry_rows import (
            _build_xlsx,
            _build_xlsx_multiyear,
            _group_rows_by_year,
        )

        if is_yearly and rows:
            xlsx_buf = _build_xlsx_multiyear(
                schema, _group_rows_by_year(rows), metadata,
            )
        else:
            xlsx_buf = _build_xlsx(title, schema, rows, metadata)

        xlsx_bytes = xlsx_buf.read()
        if existing_drive_id and await self._drive_file_exists(
            http, token, existing_drive_id
        ):
            await self._update_file_metadata(
                http, token, existing_drive_id, title
            )
            resp = await _retry_request(
                lambda: http.patch(
                    f"{DRIVE_UPLOAD_API}/{existing_drive_id}?uploadType=media",
                    content=xlsx_bytes,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": XLSX_CONTENT_TYPE,
                    },
                    params={"supportsAllDrives": "true"},
                ),
                description=f"update spreadsheet {title}",
            )
            resp.raise_for_status()
            return existing_drive_id

        drive_meta = {
            "name": title,
            "parents": [parent_drive_id],
            "mimeType": "application/vnd.google-apps.spreadsheet",
        }
        resp = await _retry_request(
            lambda: http.post(
                f"{DRIVE_UPLOAD_API}?uploadType=multipart",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "metadata": (
                        None, json.dumps(drive_meta).encode(), "application/json",
                    ),
                    "file": (None, xlsx_bytes, XLSX_CONTENT_TYPE),
                },
                params={"fields": "id", "supportsAllDrives": "true"},
            ),
            description=f"create spreadsheet {title}",
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def _save_mapping(
        self,
        db: AsyncSession,
        node_id: uuid.UUID,
        drive_file_id: str,
        file_type: str,
        cache: dict[uuid.UUID, str],
    ) -> None:
        existing = await db.execute(
            select(IsoDocDriveMappingDB).where(
                IsoDocDriveMappingDB.node_id == node_id
            )
        )
        mapping = existing.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if mapping:
            mapping.drive_file_id = drive_file_id
            mapping.drive_file_type = file_type
            mapping.last_exported_at = now
        else:
            mapping = IsoDocDriveMappingDB(
                node_id=node_id,
                drive_file_id=drive_file_id,
                drive_file_type=file_type,
                last_exported_at=now,
            )
            db.add(mapping)
        await db.commit()
        cache[node_id] = drive_file_id

    async def _cleanup_orphans(
        self,
        db: AsyncSession,
        http: httpx.AsyncClient,
        token: str,
        current_node_ids: set[uuid.UUID],
        mappings: dict[uuid.UUID, str],
    ) -> int:
        orphan_ids = [
            (nid, did) for nid, did in mappings.items()
            if nid not in current_node_ids
        ]
        for _, drive_id in orphan_ids:
            await self._delete_drive_file(http, token, drive_id)

        if orphan_ids:
            await db.execute(
                delete(IsoDocDriveMappingDB).where(
                    IsoDocDriveMappingDB.node_id.in_(
                        [nid for nid, _ in orphan_ids]
                    )
                )
            )
            await db.commit()

        return len(orphan_ids)

    def _to_html(
        self,
        title: str,
        markdown_content: str,
        metadata: IsoDocMetadataDB | None,
        category: str | None = None,
    ) -> str:
        parts = [_STYLE, f'<h1 style="font-size:24pt;margin-bottom:4pt">{_escape(title)}</h1>']

        if metadata:
            self._render_metadata_section(parts, metadata, category)

        content = _strip_leading_h1(markdown_content, title)
        body_html = _md.render(content) if content else ""
        parts.append(body_html)

        return "\n".join(parts)

    def _render_metadata_section(
        self,
        parts: list[str],
        metadata: IsoDocMetadataDB,
        category: str | None,
    ) -> None:
        pills = self._build_metadata_pills(metadata, category)
        if pills:
            parts.append(
                f'<p style="margin:8pt 0 4pt 0">{" &nbsp; ".join(pills)}</p>'
            )

        if metadata.clauses:
            parts.append(
                f'<p style="color:#666;font-size:9pt;margin:2pt 0 12pt 0">'
                f'Clauses: {_escape(", ".join(metadata.clauses))}</p>'
            )

        if metadata.changelog:
            parts.append(_render_changelog_table(metadata.changelog))

        parts.append('<hr style="border:none;border-top:1pt solid #e0e0e0;margin:16pt 0">')

    def _build_metadata_pills(
        self,
        metadata: IsoDocMetadataDB,
        category: str | None,
    ) -> list[str]:
        pills: list[str] = []
        if metadata.code:
            pills.append(f'<span style="{_PILL}">{_escape(metadata.code)}</span>')
        if metadata.standard:
            for s in metadata.standard:
                pills.append(f'<span style="{_PILL}">{_escape(s)}</span>')
        if metadata.status:
            label = STATUS_LABELS.get(metadata.status, metadata.status)
            pills.append(f'<span style="{_PILL}">{_escape(label)}</span>')
        if metadata.doc_version:
            pills.append(f'<span style="{_PILL}">v{_escape(metadata.doc_version)}</span>')
        if category:
            pills.append(f'<span style="{_PILL}">{_escape(category)}</span>')
        return pills

    # -- Google Drive API helpers --

    async def _create_folder(
        self, http: httpx.AsyncClient, token: str,
        name: str, parent_id: str | None,
    ) -> str:
        body: dict = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            body["parents"] = [parent_id]

        resp = await http.post(
            DRIVE_API,
            json=body,
            headers=_auth(token),
            params={"fields": "id", "supportsAllDrives": "true"},
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def _create_doc(
        self, http: httpx.AsyncClient, token: str,
        title: str, html: str, parent_id: str,
    ) -> str:
        doc_meta = {
            "name": title,
            "mimeType": "application/vnd.google-apps.document",
            "parents": [parent_id],
        }
        resp = await _retry_request(
            lambda: http.post(
                f"{DRIVE_UPLOAD_API}?uploadType=multipart",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "metadata": (None, json.dumps(doc_meta).encode(), "application/json"),
                    "file": (None, html.encode(), "text/html"),
                },
                params={"fields": "id", "supportsAllDrives": "true"},
            ),
            description=f"create doc {title}",
        )
        resp.raise_for_status()
        return resp.json()["id"]

    async def _update_file_metadata(
        self, http: httpx.AsyncClient, token: str,
        file_id: str, name: str,
    ) -> None:
        resp = await http.patch(
            f"{DRIVE_API}/{file_id}",
            json={"name": name},
            headers=_auth(token),
            params={"supportsAllDrives": "true"},
        )
        resp.raise_for_status()

    async def _update_file_content(
        self, http: httpx.AsyncClient, token: str,
        file_id: str, html: str,
    ) -> None:
        resp = await _retry_request(
            lambda: http.patch(
                f"{DRIVE_UPLOAD_API}/{file_id}?uploadType=media",
                content=html.encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "text/html"},
                params={"supportsAllDrives": "true"},
            ),
            description=f"update content {file_id}",
        )
        resp.raise_for_status()

    async def _drive_file_exists(
        self, http: httpx.AsyncClient, token: str, file_id: str,
    ) -> bool:
        resp = await http.get(
            f"{DRIVE_API}/{file_id}",
            headers=_auth(token),
            params={"fields": "id,trashed", "supportsAllDrives": "true"},
        )
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return not resp.json().get("trashed", False)

    async def _delete_drive_file(
        self, http: httpx.AsyncClient, token: str, file_id: str,
    ) -> None:
        resp = await http.delete(
            f"{DRIVE_API}/{file_id}",
            headers=_auth(token),
            params={"supportsAllDrives": "true"},
        )
        if resp.status_code != 404:
            resp.raise_for_status()


def _render_changelog_table(changelog: list[dict]) -> str:
    rows = [
        '<table style="border-collapse:collapse;font-size:9pt;'
        'margin:8pt 0 16pt 0;width:100%">'
        + '<tr style="background:#f5f5f5">'
        + '<th style="padding:4pt 8pt;text-align:left;border-bottom:1pt solid #ddd">Version</th>'
        + '<th style="padding:4pt 8pt;text-align:left;border-bottom:1pt solid #ddd">Date</th>'
        + '<th style="padding:4pt 8pt;text-align:left;border-bottom:1pt solid #ddd">Description</th>'
        + '<th style="padding:4pt 8pt;text-align:left;border-bottom:1pt solid #ddd">Author</th>'
        + '</tr>'
    ]
    for entry in changelog:
        v = _escape(str(entry.get("version", "")))
        d = _escape(str(entry.get("date", "")))
        desc = _escape(str(entry.get("description", "")))
        a = _escape(str(entry.get("author", "")))
        rows.append(
            f'<tr>'
            f'<td style="padding:3pt 8pt;border-bottom:1pt solid #eee">v{v}</td>'
            f'<td style="padding:3pt 8pt;border-bottom:1pt solid #eee">{d}</td>'
            f'<td style="padding:3pt 8pt;border-bottom:1pt solid #eee">{desc}</td>'
            f'<td style="padding:3pt 8pt;border-bottom:1pt solid #eee;color:#666">{a}</td>'
            f'</tr>'
        )
    rows.append("</table>")
    return "\n".join(rows)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _strip_leading_h1(content: str, title: str) -> str:
    """Remove duplicate H1 if markdown starts with the same title."""
    if not content:
        return content
    lines = content.lstrip().split("\n", 1)
    first = lines[0].strip()
    if first.startswith("# ") and first[2:].strip().lower() == title.lower():
        return lines[1].lstrip("\n") if len(lines) > 1 else ""
    return content


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
