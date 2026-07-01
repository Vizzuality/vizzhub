"""Import canonical clients from a JSON file (idempotent, keep-separate).

The JSON is a list of objects: ``[{"name": str, "code": str|null,
"primary_contact": str|null}, ...]``. Data lives outside the repo (customer
names) — pass its path as the single argument.

Behaviour:
- Slug is derived from ``name``; colliding slugs within the run are
  disambiguated with ``-2``, ``-3`` suffixes so every row stays a distinct
  client (no rows lost to dedup).
- ``code`` is unique: the first client to claim a code keeps it; later rows
  reusing that code get ``code = null`` (reassign manually later).
- Upsert by final slug: existing clients are updated, new ones inserted.
  Re-running with the same input file is a no-op beyond field refreshes.

Run: uv run python -m app.scripts.import_clients /path/to/clients.json
"""

import asyncio
import json
import re
import sys
import unicodedata

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.database import async_session_maker

logger = structlog.get_logger()


def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


def _unique_slug(base: str, claimed: set[str]) -> str:
    if base not in claimed:
        return base
    suffix = 2
    while f"{base}-{suffix}" in claimed:
        suffix += 1
    return f"{base}-{suffix}"


async def import_clients(db: AsyncSession, entries: list[dict]) -> dict[str, int]:
    existing = {c.slug: c for c in (await db.execute(select(ClientDB))).scalars().all()}
    used_codes: dict[str, str] = {c.code: c.slug for c in existing.values() if c.code}
    claimed: set[str] = set()

    created = updated = codes_cleared = skipped = 0
    for entry in entries:
        name = _clean(entry.get("name"))
        if not name:
            skipped += 1
            continue
        base = _slugify(name)
        if not base:
            skipped += 1
            continue
        slug = _unique_slug(base, claimed)
        claimed.add(slug)

        code = _clean(entry.get("code"))
        if code is not None:
            owner = used_codes.get(code)
            if owner is not None and owner != slug:
                code = None
                codes_cleared += 1
            else:
                used_codes[code] = slug
        contact = _clean(entry.get("primary_contact"))

        obj = existing.get(slug)
        if obj is None:
            obj = ClientDB(name=name, slug=slug, code=code, primary_contact=contact)
            db.add(obj)
            await db.flush()
            existing[slug] = obj
            created += 1
        else:
            obj.name = name
            obj.code = code
            obj.primary_contact = contact
            updated += 1

    stats = {
        "created": created,
        "updated": updated,
        "codes_cleared": codes_cleared,
        "skipped": skipped,
    }
    logger.info("clients_imported", **stats)
    return stats


async def main(path: str) -> None:
    with open(path, encoding="utf-8") as fh:
        entries = json.load(fh)
    async with async_session_maker() as db:
        stats = await import_clients(db, entries)
        await db.commit()
    print(
        f"created={stats['created']} updated={stats['updated']} "
        f"codes_cleared={stats['codes_cleared']} skipped={stats['skipped']}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m app.scripts.import_clients <clients.json>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(main(sys.argv[1]))
