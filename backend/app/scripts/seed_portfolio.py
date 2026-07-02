"""Seed portfolio taxonomies and canonical clients (idempotent).

Run: uv run python -m app.scripts.seed_portfolio
"""

import asyncio
import re
import unicodedata

import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.taxonomy import Cardinality, TaxonomyDB, TaxonomyTermDB
from app.database import async_session_maker

logger = structlog.get_logger()

# Closed lists confirmed with the portfolio manager. Terms editable later via admin.
TAXONOMY_SEED = [
    {
        "slug": "impact-area",
        "name": "Impact Area",
        "cardinality": Cardinality.MULTI,
        "allows_primary": True,
        "terms": ["Nature", "Climate", "People", "Oceans & Water", "Food & Land Systems"],
    },
    {
        "slug": "service",
        "name": "Service Provided",
        "cardinality": Cardinality.MULTI,
        "allows_primary": True,
        "terms": ["Tools", "Strategic", "Communications", "Scientific", "Maintenance"],
    },
    {
        "slug": "client-type",
        "name": "Client Type",
        "cardinality": Cardinality.SINGLE,
        "allows_primary": False,
        "terms": ["NGO", "Government", "Private", "Academic", "Multilateral"],
    },
    {
        "slug": "geography",
        "name": "Geography",
        "cardinality": Cardinality.MULTI,
        "allows_primary": False,
        "terms": ["Global", "Europe", "Africa", "Asia", "Americas", "Oceania"],
    },
    {
        "slug": "topics",
        "name": "Topics",
        "cardinality": Cardinality.MULTI,
        "allows_primary": False,
        "terms": [],
    },
]


def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


async def seed_taxonomies(db: AsyncSession) -> int:
    created = 0
    for idx, spec in enumerate(TAXONOMY_SEED):
        tax = (
            await db.execute(select(TaxonomyDB).where(TaxonomyDB.slug == spec["slug"]))
        ).scalar_one_or_none()
        if tax is None:
            tax = TaxonomyDB(
                slug=spec["slug"],
                name=spec["name"],
                cardinality=spec["cardinality"],
                allows_primary=spec["allows_primary"],
                sort_order=idx,
            )
            db.add(tax)
            await db.flush()
        existing_terms = {
            t.slug
            for t in (
                await db.execute(select(TaxonomyTermDB).where(TaxonomyTermDB.taxonomy_id == tax.id))
            )
            .scalars()
            .all()
        }
        for t_idx, term_name in enumerate(spec["terms"]):
            term_slug = _slugify(term_name)
            if term_slug in existing_terms:
                continue
            db.add(
                TaxonomyTermDB(taxonomy_id=tax.id, slug=term_slug, name=term_name, sort_order=t_idx)
            )
            created += 1
    logger.info("taxonomy_seeded", terms_created=created)
    return created


async def seed_clients(db: AsyncSession) -> tuple[int, int]:
    # 1. Distinct client names from the latest accrual import run.
    # Note: accrual_import_runs uses completed_at (not created_at) for ordering.
    names = (
        (
            await db.execute(
                text(
                    """
        SELECT DISTINCT btrim(client) AS client
        FROM accrual_excel_rows
        WHERE client IS NOT NULL AND btrim(client) <> ''
          AND import_run_id = (
            SELECT id FROM accrual_import_runs
            WHERE completed_at IS NOT NULL
            ORDER BY completed_at DESC LIMIT 1
          )
        """
                )
            )
        )
        .scalars()
        .all()
    )
    clients_created = 0
    slug_to_id: dict[str, str] = {}
    for name in names:
        slug = _slugify(name)
        if not slug:
            continue
        existing = (
            await db.execute(select(ClientDB).where(ClientDB.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            slug_to_id[slug] = str(existing.id)
            continue
        obj = ClientDB(name=name, slug=slug)
        db.add(obj)
        await db.flush()
        slug_to_id[slug] = str(obj.id)
        clients_created += 1

    # 2. Best-effort project→client via excel_code bridge. Never overwrite a non-null client_id.
    # Use the same _slugify() as step 1 to avoid accent-folding mismatch with SQL regexp_replace.
    bridge_rows = (
        await db.execute(
            text(
                """
        SELECT DISTINCT alp.project_id, btrim(er.client) AS client
        FROM accrual_excel_rows er
        JOIN accrual_lines al ON al.excel_code = er.excel_code
        JOIN accrual_line_projects alp ON alp.line_id = al.id
        WHERE er.client IS NOT NULL AND btrim(er.client) <> ''
        """
            )
        )
    ).all()
    linked = 0
    for row in bridge_rows:
        cid = slug_to_id.get(_slugify(row.client))
        if cid is None:
            continue
        result = await db.execute(
            text("UPDATE projects SET client_id = :cid WHERE id = :pid AND client_id IS NULL"),
            {"cid": cid, "pid": row.project_id},
        )
        linked += result.rowcount
    logger.info("clients_seeded", clients_created=clients_created, projects_linked=linked)
    return clients_created, linked


async def link_projects_by_code(db: AsyncSession) -> int:
    """Link projects to clients by matching a dotted-code prefix to clients.code.

    Deterministic and idempotent: only sets client_id where it IS NULL, and
    clients.code is unique so each prefix maps to at most one client. Union of
    two prefix sources: the project's own code, and its accrual excel_code
    (via the accrual_line_projects bridge). Returns the number of rows linked.
    """
    result = await db.execute(
        text(
            """
            WITH candidates AS (
                SELECT p.id AS project_id, c.id AS client_id
                FROM projects p
                JOIN clients c ON c.code = split_part(p.code, '.', 1)
                WHERE p.code IS NOT NULL AND p.code <> '' AND p.client_id IS NULL
                UNION
                SELECT alp.project_id, c.id AS client_id
                FROM accrual_line_projects alp
                JOIN accrual_lines al ON al.id = alp.line_id
                JOIN clients c ON c.code = split_part(al.excel_code, '.', 1)
                JOIN projects p2 ON p2.id = alp.project_id
                WHERE al.excel_code IS NOT NULL AND al.excel_code <> ''
                  AND p2.client_id IS NULL
            )
            UPDATE projects p
            SET client_id = candidates.client_id
            FROM candidates
            WHERE p.id = candidates.project_id AND p.client_id IS NULL
            """
        )
    )
    linked = result.rowcount
    logger.info("projects_linked_by_code", projects_linked=linked)
    return linked


async def main() -> None:
    async with async_session_maker() as db:
        await seed_taxonomies(db)
        await seed_clients(db)
        await link_projects_by_code(db)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
