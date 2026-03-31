"""Import ISO docs data from JSON export into the database.

Usage:
    python scripts/import_iso_docs.py <json_file> [--clear]

    --clear  Delete existing ISO docs data before importing.

Connects to the database configured in DATABASE_URL.
Inserts in FK order: nodes (parents first), then versions + metadata.
"""

import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, delete, text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.core.models.user import UserDB  # noqa: F401
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB


def _uuid(value: str | None) -> UUID | None:
    return UUID(value) if value else None


async def import_iso_docs(json_path: str, clear: bool = False) -> None:
    path = Path(json_path)
    if not path.exists():
        print(f"Error: {json_path} not found")
        sys.exit(1)

    data = json.loads(path.read_text())
    print(f"Export from: {data['exported_at']}")
    print(f"Contains: {data['counts']['nodes']} nodes, "
          f"{data['counts']['versions']} versions, "
          f"{data['counts']['metadata']} metadata records")

    async with async_session_maker() as db:
        if clear:
            await db.execute(delete(IsoDocMetadataDB))
            await db.execute(delete(IsoDocVersionDB))
            await db.execute(delete(IsoDocNodeDB))
            await db.flush()
            print("Cleared existing ISO docs data")

        existing = await db.execute(select(IsoDocNodeDB.id).limit(1))
        if existing.scalar_one_or_none() is not None and not clear:
            print("ISO docs already has data. Use --clear to replace it.")
            return

        # Insert nodes: parents first (parent_id=None), then children
        parent_nodes = [n for n in data["nodes"] if n["parent_id"] is None]
        child_nodes = [n for n in data["nodes"] if n["parent_id"] is not None]

        for node_data in parent_nodes + child_nodes:
            await db.execute(
                text("""
                    INSERT INTO iso_doc_nodes
                        (id, title, slug, type, parent_id, position,
                         created_by_id, updated_by_id, created_at, updated_at)
                    VALUES
                        (:id, :title, :slug, :type, :parent_id, :position,
                         :created_by_id, :updated_by_id,
                         COALESCE(:created_at::timestamptz, now()),
                         COALESCE(:updated_at::timestamptz, now()))
                """),
                {
                    "id": node_data["id"],
                    "title": node_data["title"],
                    "slug": node_data["slug"],
                    "type": node_data["type"],
                    "parent_id": node_data["parent_id"],
                    "position": node_data["position"],
                    "created_by_id": node_data.get("created_by_id"),
                    "updated_by_id": node_data.get("updated_by_id"),
                    "created_at": node_data.get("created_at"),
                    "updated_at": node_data.get("updated_at"),
                },
            )
        print(f"  Inserted {len(data['nodes'])} nodes")

        for v in data["versions"]:
            await db.execute(
                text("""
                    INSERT INTO iso_doc_versions
                        (id, node_id, content, version, created_by_id, created_at)
                    VALUES
                        (:id, :node_id, :content, :version, :created_by_id,
                         COALESCE(:created_at::timestamptz, now()))
                """),
                {
                    "id": v["id"],
                    "node_id": v["node_id"],
                    "content": v["content"],
                    "version": v["version"],
                    "created_by_id": v.get("created_by_id"),
                    "created_at": v.get("created_at"),
                },
            )
        print(f"  Inserted {len(data['versions'])} versions")

        for m in data["metadata"]:
            await db.execute(
                text("""
                    INSERT INTO iso_doc_metadata
                        (id, node_id, code, standard, clauses, category,
                         doc_version, status, original_filename, changelog,
                         created_at, updated_at)
                    VALUES
                        (:id, :node_id, :code, :standard, :clauses,
                         :category::iso_doc_category, :doc_version,
                         :status::iso_doc_status, :original_filename,
                         :changelog::jsonb,
                         COALESCE(:created_at::timestamptz, now()),
                         COALESCE(:updated_at::timestamptz, now()))
                """),
                {
                    "id": m["id"],
                    "node_id": m["node_id"],
                    "code": m.get("code"),
                    "standard": m.get("standard"),
                    "clauses": m.get("clauses"),
                    "category": m.get("category"),
                    "doc_version": m.get("doc_version"),
                    "status": m.get("status"),
                    "original_filename": m.get("original_filename"),
                    "changelog": json.dumps(m["changelog"]) if m.get("changelog") else None,
                    "created_at": m.get("created_at"),
                    "updated_at": m.get("updated_at"),
                },
            )
        print(f"  Inserted {len(data['metadata'])} metadata records")

        await db.commit()
        print("Import complete")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_iso_docs.py <json_file> [--clear]")
        sys.exit(1)

    json_file = sys.argv[1]
    clear_flag = "--clear" in sys.argv
    asyncio.run(import_iso_docs(json_file, clear=clear_flag))
