"""Portfolio data access — program search, detail, and filtered listing."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import TaxonomyDB, TaxonomyTermDB
from app.core.services.program_catalog import (
    build_program_detail,
    build_program_index,
    escape_like,
    list_program_stages,
    search_query_candidates,
)
from app.modules.portfolio.schemas.programs import ProgramSummary

BASE_URL = "https://hub.vizzuality.com"
MAX_LIMIT = 50


async def search_programs(session: AsyncSession, query: str, limit: int = 10) -> list[dict]:
    """Rank programs by name match first, then ts_rank over the narrative vector.

    Mirrors the API index search: strict AND pass first, OR fallback when
    nothing matches (websearch ANDs every token).
    """
    needle = query.strip()
    if len(needle) < 2:
        return []
    limit = max(1, min(limit, MAX_LIMIT))

    name_match = ProgramDB.name.ilike(f"%{escape_like(needle)}%", escape="\\")
    narrative = func.concat_ws(
        " ",
        PortfolioProfileDB.objective,
        PortfolioProfileDB.short_description,
        PortfolioProfileDB.impact_story,
        PortfolioProfileDB.web_copy,
        PortfolioProfileDB.main_partner,
    )

    rows = []
    for query_text in search_query_candidates(needle):
        tsq = func.websearch_to_tsquery("english", query_text)
        vector_match = PortfolioProfileDB.search_vector.op("@@")(tsq)
        snippet = func.ts_headline("english", narrative, tsq, "MaxFragments=2, MaxWords=25")
        rows = (
            await session.execute(
                select(
                    ProgramDB.id,
                    ProgramDB.name,
                    PortfolioProfileDB.stage,
                    vector_match.label("is_vector_match"),
                    snippet.label("snippet"),
                    func.coalesce(PortfolioProfileDB.short_description, "").label("fallback"),
                )
                .outerjoin(PortfolioProfileDB, PortfolioProfileDB.program_id == ProgramDB.id)
                .where(name_match | vector_match)
                .order_by(
                    name_match.desc(),
                    func.coalesce(func.ts_rank(PortfolioProfileDB.search_vector, tsq), 0).desc(),
                    ProgramDB.name,
                )
                .limit(limit)
            )
        ).all()
        if rows:
            break
    return [
        {
            "program_id": str(row.id),
            "name": row.name,
            "stage": row.stage,
            "snippet": row.snippet if row.is_vector_match else row.fallback[:150],
            "url": f"{BASE_URL}/admin/portfolio/programs/{row.id}",
        }
        for row in rows
    ]


async def get_program(session: AsyncSession, program_id: UUID) -> dict | None:
    """Full program detail: profile narrative, tags, clients, project iterations."""
    summary = await build_program_detail(session, program_id)
    if summary is None:
        return None
    data = summary.model_dump(mode="json")
    data["program_id"] = data.pop("id")
    data["url"] = f"{BASE_URL}/admin/portfolio/programs/{program_id}"
    return data


async def _resolve_term_ids(
    session: AsyncSession, tags: list[str]
) -> tuple[list[UUID], list[str]]:
    wanted = {t.strip().lower() for t in tags if t.strip()}
    rows = (
        await session.execute(
            select(TaxonomyTermDB.id, TaxonomyTermDB.name).where(
                func.lower(TaxonomyTermDB.name).in_(wanted)
            )
        )
    ).all()
    matched = {name.lower() for _, name in rows}
    return [tid for tid, _ in rows], sorted(wanted - matched)


async def _resolve_client_filter(session: AsyncSession, client: str) -> UUID | dict:
    """Resolve a client name substring to a single client id, or an error dict."""
    needle = escape_like(client.strip())
    rows = (
        await session.execute(
            select(ClientDB.id, ClientDB.name)
            .where(ClientDB.name.ilike(f"%{needle}%", escape="\\"))
            .order_by(ClientDB.name)
        )
    ).all()
    if not rows:
        return {"error": f"No client matches '{client}'"}
    if len(rows) > 1:
        return {
            "error": f"Client '{client}' is ambiguous — use a more specific name",
            "candidates": [name for _, name in rows[:10]],
        }
    return rows[0].id


def _compact_program(p: ProgramSummary) -> dict:
    years = [y for it in p.projects for y in (it.start_year, it.end_year) if y is not None]
    short = p.profile.short_description if p.profile else None
    return {
        "program_id": str(p.id),
        "name": p.name,
        "stage": p.profile.stage if p.profile else None,
        "short_description": short[:200] if short else None,
        "tags": [t.name for t in p.terms],
        "clients": [c.name for c in p.clients],
        "projects_count": len(p.projects),
        "years": f"{min(years)}-{max(years)}" if years else None,
        "url": f"{BASE_URL}/admin/portfolio/programs/{p.id}",
    }


async def list_programs(
    session: AsyncSession,
    *,
    stage: str | None = None,
    tags: list[str] | None = None,
    client: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """Compact paginated program listing with server-side name→id filter resolution."""
    limit = max(1, min(limit, MAX_LIMIT))
    page = max(1, page)

    term_ids: list[UUID] | None = None
    unmatched_tags: list[str] = []
    if tags:
        term_ids, unmatched_tags = await _resolve_term_ids(session, tags)
        if not term_ids:
            return {
                "programs": [],
                "total": 0,
                "pages": 1,
                "page": page,
                "unmatched_tags": unmatched_tags,
            }

    client_id: UUID | None = None
    if client and client.strip():
        resolved = await _resolve_client_filter(session, client)
        if isinstance(resolved, dict):
            return resolved
        client_id = resolved

    resp = await build_program_index(
        session, term_ids=term_ids, client_id=client_id, stage=stage, page=page, n=limit
    )
    programs = [_compact_program(p) for p in resp.programs]
    out = {"programs": programs, "total": resp.total, "pages": resp.pages, "page": page}
    if unmatched_tags:
        out["unmatched_tags"] = unmatched_tags
    return out


async def get_taxonomies(session: AsyncSession) -> dict:
    """Active taxonomies with their active terms, plus the existing stage values.

    Makes the list_programs `tags`/`stage` filters (and set_tags term names)
    discoverable without guessing.
    """
    taxonomies = (
        (
            await session.execute(
                select(TaxonomyDB)
                .where(TaxonomyDB.is_active.is_(True))
                .order_by(TaxonomyDB.sort_order, TaxonomyDB.name)
            )
        )
        .scalars()
        .all()
    )
    term_rows = (
        await session.execute(
            select(TaxonomyTermDB)
            .where(TaxonomyTermDB.is_active.is_(True))
            .order_by(TaxonomyTermDB.sort_order, TaxonomyTermDB.name)
        )
    ).scalars()
    terms_by_taxonomy: dict = {}
    for term in term_rows:
        terms_by_taxonomy.setdefault(term.taxonomy_id, []).append(term.name)
    return {
        "taxonomies": [
            {
                "slug": t.slug,
                "name": t.name,
                "cardinality": t.cardinality.value,
                "allows_primary": t.allows_primary,
                "terms": terms_by_taxonomy.get(t.id, []),
            }
            for t in taxonomies
        ],
        "stages": await list_program_stages(session),
    }


async def get_clients(session: AsyncSession) -> list[dict]:
    """All clients with how many projects each has (0-project clients included)."""
    projects_count = (
        select(func.count())
        .where(ProjectDB.client_id == ClientDB.id)
        .correlate(ClientDB)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(ClientDB.id, ClientDB.name, projects_count.label("projects_count")).order_by(
                ClientDB.name
            )
        )
    ).all()
    return [
        {"client_id": str(row.id), "name": row.name, "projects_count": row.projects_count}
        for row in rows
    ]
