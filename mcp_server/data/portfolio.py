"""Portfolio data access — full-text program search over profile narrative."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB

BASE_URL = "https://hub.vizzuality.com"
MAX_LIMIT = 50


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


async def search_programs(session: AsyncSession, query: str, limit: int = 10) -> list[dict]:
    """Rank programs by name match first, then ts_rank over the narrative vector."""
    needle = query.strip()
    if len(needle) < 2:
        return []
    limit = max(1, min(limit, MAX_LIMIT))

    tsq = func.websearch_to_tsquery("english", needle)
    name_match = ProgramDB.name.ilike(f"%{_escape_like(needle)}%", escape="\\")
    vector_match = PortfolioProfileDB.search_vector.op("@@")(tsq)
    narrative = func.concat_ws(
        " ",
        PortfolioProfileDB.objective,
        PortfolioProfileDB.short_description,
        PortfolioProfileDB.impact_story,
        PortfolioProfileDB.web_copy,
        PortfolioProfileDB.main_partner,
    )
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
