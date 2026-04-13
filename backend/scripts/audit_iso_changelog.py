"""Report ISO metadata rows with malformed changelog entries.

An entry is malformed if it is missing any of the four required fields
(version, date, author, description). The script only REPORTS rows; it
does not modify data.

Usage (from repo root):
    PYTHONPATH=backend python backend/scripts/audit_iso_changelog.py

Against prod via SSM:
    aws ssm start-session --target i-097d6d92ab30d9622
    # then inside the session:
    docker exec -i hub-backend python /opt/audit.py
"""

from __future__ import annotations

import asyncio
import json

from sqlalchemy import text

from app.database import async_session_maker

REQUIRED_FIELDS = ("version", "date", "author", "description")

AUDIT_SQL = text(
    """
    SELECT
        n.slug AS node_slug,
        n.title,
        m.id AS metadata_id,
        m.changelog
    FROM iso_doc_metadata m
    JOIN iso_doc_nodes n ON n.id = m.node_id
    WHERE m.changelog IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM jsonb_array_elements(m.changelog) e
          WHERE NOT (e ? 'version')
             OR NOT (e ? 'date')
             OR NOT (e ? 'author')
             OR NOT (e ? 'description')
      )
    ORDER BY m.updated_at DESC
    """
)


async def main() -> None:
    async with async_session_maker() as session:
        rows = (await session.execute(AUDIT_SQL)).all()

    if not rows:
        print("OK: no rows with malformed changelog entries.")
        return

    print(f"FOUND {len(rows)} row(s) with malformed changelog entries:")
    for slug, title, metadata_id, changelog in rows:
        bad_indices = [
            i
            for i, entry in enumerate(changelog or [])
            if not isinstance(entry, dict)
            or any(field not in entry for field in REQUIRED_FIELDS)
        ]
        print(
            json.dumps(
                {
                    "node_slug": slug,
                    "title": title,
                    "metadata_id": str(metadata_id),
                    "bad_entry_indices": bad_indices,
                    "entry_count": len(changelog or []),
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
