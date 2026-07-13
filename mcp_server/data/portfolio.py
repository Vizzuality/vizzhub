"""Portfolio data access — program search, detail, and filtered listing."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.taxonomy import TaxonomyTermDB
from app.core.services.program_catalog import (
    build_program_detail,
    build_program_index,
    escape_like,
    search_query_candidates,
)

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
        needle = escape_like(client.strip())
        client_rows = (
            await session.execute(
                select(ClientDB.id, ClientDB.name)
                .where(ClientDB.name.ilike(f"%{needle}%", escape="\\"))
                .order_by(ClientDB.name)
            )
        ).all()
        if not client_rows:
            return {"error": f"No client matches '{client}'"}
        if len(client_rows) > 1:
            return {
                "error": f"Client '{client}' is ambiguous — use a more specific name",
                "candidates": [name for _, name in client_rows[:10]],
            }
        client_id = client_rows[0].id

    resp = await build_program_index(
        session, term_ids=term_ids, client_id=client_id, stage=stage, page=page, n=limit
    )
    programs = []
    for p in resp.programs:
        years = [y for it in p.projects for y in (it.start_year, it.end_year) if y is not None]
        short = p.profile.short_description if p.profile else None
        programs.append(
            {
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
        )
    out = {"programs": programs, "total": resp.total, "pages": resp.pages, "page": page}
    if unmatched_tags:
        out["unmatched_tags"] = unmatched_tags
    return out
