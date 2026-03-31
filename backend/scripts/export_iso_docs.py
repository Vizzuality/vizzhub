"""Export ISO docs data (nodes, versions, metadata) from DB to JSON.

Usage:
    python scripts/export_iso_docs.py [output_file]

Defaults to iso_docs_export.json in the current directory.
Connects to the database configured in DATABASE_URL.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.core.models.user import UserDB  # noqa: F401
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.iso_docs.models.metadata import IsoDocMetadataDB


def _serialize(obj: object) -> str:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Cannot serialize {type(obj)}")


async def export_iso_docs(output_path: str) -> None:
    async with async_session_maker() as db:
        nodes_result = await db.execute(
            select(IsoDocNodeDB).order_by(IsoDocNodeDB.position)
        )
        nodes = nodes_result.scalars().unique().all()

        versions_result = await db.execute(
            select(IsoDocVersionDB).order_by(
                IsoDocVersionDB.node_id, IsoDocVersionDB.version
            )
        )
        versions = versions_result.scalars().all()

        metadata_result = await db.execute(select(IsoDocMetadataDB))
        metadata_records = metadata_result.scalars().all()

    data = {
        "exported_at": datetime.utcnow().isoformat(),
        "counts": {
            "nodes": len(nodes),
            "versions": len(versions),
            "metadata": len(metadata_records),
        },
        "nodes": [
            {
                "id": str(n.id),
                "title": n.title,
                "slug": n.slug,
                "type": n.type,
                "parent_id": str(n.parent_id) if n.parent_id else None,
                "position": n.position,
                "created_by_id": str(n.created_by_id) if n.created_by_id else None,
                "updated_by_id": str(n.updated_by_id) if n.updated_by_id else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
                "updated_at": n.updated_at.isoformat() if n.updated_at else None,
            }
            for n in nodes
        ],
        "versions": [
            {
                "id": str(v.id),
                "node_id": str(v.node_id),
                "content": v.content,
                "version": v.version,
                "created_by_id": str(v.created_by_id) if v.created_by_id else None,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
        "metadata": [
            {
                "id": str(m.id),
                "node_id": str(m.node_id),
                "code": m.code,
                "standard": m.standard,
                "clauses": m.clauses,
                "category": m.category,
                "classification": m.classification,
                "doc_version": m.doc_version,
                "status": m.status,
                "original_filename": m.original_filename,
                "changelog": m.changelog,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in metadata_records
        ],
    }

    Path(output_path).write_text(json.dumps(data, indent=2, default=_serialize))
    print(f"Exported {len(nodes)} nodes, {len(versions)} versions, "
          f"{len(metadata_records)} metadata records to {output_path}")


if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "iso_docs_export.json"
    asyncio.run(export_iso_docs(output))
