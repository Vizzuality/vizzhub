"""Tests for MCP Portfolio tools — full-text program search."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from mcp_server.data.base import override_session
from mcp_server.server import create_mcp_server


def _parse_tool_result(result) -> dict | list:
    content_blocks = result[0]
    return json.loads(content_blocks[0].text)


@pytest_asyncio.fixture
async def seed_programs(db_session: AsyncSession) -> None:
    narrative = ProgramDB(name="Alpha Program")
    named = ProgramDB(name="Mangrove Atlas")
    db_session.add_all([narrative, named])
    await db_session.flush()
    db_session.add(
        PortfolioProfileDB(
            program_id=narrative.id,
            stage="live",
            objective="Restoring mangrove ecosystems in coastal areas",
        )
    )
    db_session.add(PortfolioProfileDB(program_id=named.id, stage="live"))
    await db_session.commit()


@pytest.mark.asyncio
async def test_search_returns_ranked_matches_with_snippets(
    db_session: AsyncSession, seed_programs: None
) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "portfolio_search_programs", {"query": "mangrove"}
        )
    rows = _parse_tool_result(result)
    names = [r["name"] for r in rows]
    # "Mangrove Atlas" matches by name (ILIKE) — ranks first
    # "Alpha Program" matches by narrative (objective contains "mangrove") — ranks second
    assert names == ["Mangrove Atlas", "Alpha Program"]
    # narrative match carries a ts_headline snippet with <b> highlights
    alpha = next(r for r in rows if r["name"] == "Alpha Program")
    assert "<b>" in alpha["snippet"]
    assert alpha["url"].endswith(f"/admin/portfolio/programs/{alpha['program_id']}")


@pytest.mark.asyncio
async def test_search_or_fallback_when_strict_query_matches_nothing(
    db_session: AsyncSession, seed_programs: None
) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "portfolio_search_programs", {"query": "zzqq mangrove restoration"}
        )
    rows = _parse_tool_result(result)
    # strict AND pass yields nothing ('zzqq'); the OR fallback recovers the
    # narrative match (name ILIKE needs the full phrase, so Atlas stays out)
    assert [r["name"] for r in rows] == ["Alpha Program"]


@pytest.mark.asyncio
async def test_search_limit_clamped(db_session: AsyncSession, seed_programs: None) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "portfolio_search_programs", {"query": "mangrove", "limit": 999}
        )
    assert len(_parse_tool_result(result)) <= 50
