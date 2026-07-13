"""Tests for MCP Portfolio tools — search, detail, listing, facets, and writes."""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import Cardinality, EntityTermDB, TaxonomyDB, TaxonomyTermDB
from app.core.models.user import UserDB
from mcp_server.data.base import McpUserContext, override_mcp_user, override_session
from mcp_server.server import create_mcp_server


def _parse_tool_result(result) -> dict | list:
    content_blocks = result[0]
    return json.loads(content_blocks[0].text)


@pytest_asyncio.fixture
async def seed_programs(db_session: AsyncSession) -> dict:
    narrative = ProgramDB(name="Alpha Program")
    named = ProgramDB(name="Mangrove Atlas")
    db_session.add_all([narrative, named])
    await db_session.flush()
    db_session.add(
        PortfolioProfileDB(
            program_id=narrative.id,
            stage="live",
            short_description="Coastal restoration programme",
            objective="Restoring mangrove ecosystems in coastal areas",
        )
    )
    db_session.add(PortfolioProfileDB(program_id=named.id, stage="proposal"))

    tax = TaxonomyDB(slug="geography", name="Geography", cardinality=Cardinality.MULTI)
    db_session.add(tax)
    await db_session.flush()
    europe = TaxonomyTermDB(taxonomy_id=tax.id, slug="europe", name="Europe")
    db_session.add(europe)
    await db_session.flush()
    db_session.add(EntityTermDB(term_id=europe.id, taxonomy_id=tax.id, program_id=narrative.id))

    acme = ClientDB(name="Acme", slug="acme")
    db_session.add(acme)
    await db_session.flush()
    db_session.add(
        ProjectDB(
            name="Alpha 2024",
            is_billable=True,
            is_absence=False,
            status="live",
            program_id=narrative.id,
            client_id=acme.id,
        )
    )
    await db_session.commit()
    return {"narrative_id": str(narrative.id), "named_id": str(named.id)}


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


@pytest.mark.asyncio
async def test_get_program_returns_full_detail(
    db_session: AsyncSession, seed_programs: dict
) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "portfolio_get_program", {"program_id": seed_programs["narrative_id"]}
        )
    detail = _parse_tool_result(result)
    assert detail["name"] == "Alpha Program"
    assert detail["profile"]["objective"].startswith("Restoring mangrove")
    assert [t["name"] for t in detail["terms"]] == ["Europe"]
    assert detail["terms"][0]["taxonomy_slug"] == "geography"
    assert [c["name"] for c in detail["clients"]] == ["Acme"]
    assert [p["name"] for p in detail["projects"]] == ["Alpha 2024"]
    assert detail["url"].endswith(f"/admin/portfolio/programs/{seed_programs['narrative_id']}")


@pytest.mark.asyncio
async def test_get_program_unknown_and_invalid_id(
    db_session: AsyncSession, seed_programs: dict
) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        missing = await server.call_tool(
            "portfolio_get_program",
            {"program_id": "00000000-0000-0000-0000-000000000001"},
        )
        malformed = await server.call_tool("portfolio_get_program", {"program_id": "nope"})
    assert "not found" in _parse_tool_result(missing)["error"]
    assert "Invalid program_id" in _parse_tool_result(malformed)["error"]


@pytest.mark.asyncio
async def test_list_programs_unfiltered_paginates(
    db_session: AsyncSession, seed_programs: dict
) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("portfolio_list_programs", {"limit": 1})
    payload = _parse_tool_result(result)
    assert payload["total"] == 2
    assert payload["pages"] == 2
    assert payload["page"] == 1
    # ordered by name: Alpha Program first, compact shape with tags/clients
    (row,) = payload["programs"]
    assert row["name"] == "Alpha Program"
    assert row["tags"] == ["Europe"]
    assert row["clients"] == ["Acme"]
    assert row["projects_count"] == 1


@pytest.mark.asyncio
async def test_list_programs_filters_by_stage_and_tag_name(
    db_session: AsyncSession, seed_programs: dict
) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        by_stage = await server.call_tool("portfolio_list_programs", {"stage": "proposal"})
        by_tag = await server.call_tool("portfolio_list_programs", {"tags": ["europe"]})
        bad_tag = await server.call_tool("portfolio_list_programs", {"tags": ["Neverland"]})
    assert [p["name"] for p in _parse_tool_result(by_stage)["programs"]] == ["Mangrove Atlas"]
    # tag names resolve case-insensitively to term ids
    assert [p["name"] for p in _parse_tool_result(by_tag)["programs"]] == ["Alpha Program"]
    bad = _parse_tool_result(bad_tag)
    assert bad["programs"] == []
    assert bad["unmatched_tags"] == ["neverland"]


@pytest.mark.asyncio
async def test_list_programs_resolves_client_by_name(
    db_session: AsyncSession, seed_programs: dict
) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        by_client = await server.call_tool("portfolio_list_programs", {"client": "acm"})
        no_client = await server.call_tool("portfolio_list_programs", {"client": "Globex"})
    assert [p["name"] for p in _parse_tool_result(by_client)["programs"]] == ["Alpha Program"]
    assert "No client matches" in _parse_tool_result(no_client)["error"]


@pytest.mark.asyncio
async def test_get_taxonomies_lists_terms_and_stages(
    db_session: AsyncSession, seed_programs: dict
) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("portfolio_get_taxonomies", {})
    payload = _parse_tool_result(result)
    (geography,) = payload["taxonomies"]
    assert geography["slug"] == "geography"
    assert geography["cardinality"] == "multi"
    assert geography["terms"] == ["Europe"]
    assert payload["stages"] == ["live", "proposal"]


@pytest.mark.asyncio
async def test_get_clients_with_project_counts(
    db_session: AsyncSession, seed_programs: dict
) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("portfolio_get_clients", {})
    (acme,) = _parse_tool_result(result)
    assert acme["name"] == "Acme"
    assert acme["projects_count"] == 1


# ---------------------------------------------------------------------------
# Write tools — command queue round-trips
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def manager_ctx(db_session: AsyncSession) -> McpUserContext:
    user = UserDB(email="portfolio-manager@vizzuality.com", name="Portfolio Manager")
    db_session.add(user)
    await db_session.flush()
    return McpUserContext(
        user_id=str(user.id),
        email=user.email,
        roles=["admin"],
        permissions=["*"],
    )


@pytest.mark.asyncio
async def test_update_profile_enqueue_and_approve(
    db_session: AsyncSession, seed_programs: dict, manager_ctx: McpUserContext
) -> None:
    server = create_mcp_server()
    async with override_session(db_session), override_mcp_user(manager_ctx):
        queued = await server.call_tool(
            "portfolio_update_profile",
            {
                "program_id": seed_programs["narrative_id"],
                "objective": "Updated objective",
                "main_partner": "",
            },
        )
        data = _parse_tool_result(queued)
        assert data["status"] == "queued"
        assert "Alpha Program" in data["summary"]
        assert "clear main_partner" in data["summary"]

        approved = await server.call_tool(
            "approve_command", {"command_id": data["command_id"]}
        )
    approve_data = _parse_tool_result(approved)
    assert approve_data["status"] == "executed"
    assert approve_data["result"]["profile"]["objective"] == "Updated objective"
    assert approve_data["result"]["profile"]["main_partner"] is None


@pytest.mark.asyncio
async def test_set_tags_enqueue_and_approve(
    db_session: AsyncSession, seed_programs: dict, manager_ctx: McpUserContext
) -> None:
    server = create_mcp_server()
    async with override_session(db_session), override_mcp_user(manager_ctx):
        queued = await server.call_tool(
            "portfolio_set_tags",
            {
                "program_id": seed_programs["named_id"],
                "taxonomy": "geography",
                "term_names": ["europe"],
            },
        )
        data = _parse_tool_result(queued)
        assert data["status"] == "queued"
        assert "geography" in data["summary"]

        approved = await server.call_tool(
            "approve_command", {"command_id": data["command_id"]}
        )
    approve_data = _parse_tool_result(approved)
    assert approve_data["status"] == "executed"
    assert [t["name"] for t in approve_data["result"]["terms"]] == ["Europe"]


@pytest.mark.asyncio
async def test_create_and_rename_program_via_queue(
    db_session: AsyncSession, seed_programs: dict, manager_ctx: McpUserContext
) -> None:
    server = create_mcp_server()
    async with override_session(db_session), override_mcp_user(manager_ctx):
        queued = await server.call_tool("portfolio_create_program", {"name": "Gamma Program"})
        data = _parse_tool_result(queued)
        assert data["summary"] == "Create program **Gamma Program**"
        approved = _parse_tool_result(
            await server.call_tool("approve_command", {"command_id": data["command_id"]})
        )
        assert approved["status"] == "executed"
        new_id = approved["result"]["program_id"]

        renamed = _parse_tool_result(
            await server.call_tool(
                "portfolio_rename_program", {"program_id": new_id, "name": "Gamma v2"}
            )
        )
        assert "Gamma Program" in renamed["summary"] and "Gamma v2" in renamed["summary"]
        rename_approved = _parse_tool_result(
            await server.call_tool("approve_command", {"command_id": renamed["command_id"]})
        )
    assert rename_approved["status"] == "executed"
    assert rename_approved["result"]["name"] == "Gamma v2"
