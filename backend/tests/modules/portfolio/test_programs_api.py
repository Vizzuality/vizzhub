"""Integration tests for /api/portfolio/programs (F2 catalogue)."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.client import ClientDB
from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import Cardinality, EntityTermDB, TaxonomyDB, TaxonomyTermDB
from app.database import get_db
from app.main import app

USER_ID = "00000000-0000-0000-0000-000000000042"


def _token(*permissions: str) -> TokenData:
    return TokenData(
        user_id=USER_ID, email="t@test.com", roles=["user"], permissions=list(permissions)
    )


def _make_client(db_session: AsyncSession, token: TokenData) -> AsyncClient:
    async def override_get_db():
        yield db_session

    async def override_get_current_user() -> TokenData:
        return token

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def viewer(db_session: AsyncSession):
    client = _make_client(db_session, _token("portfolio:view"))
    async with client as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def manager(db_session: AsyncSession):
    client = _make_client(db_session, _token("portfolio:view", "portfolio:manage"))
    async with client as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_catalogue(db: AsyncSession) -> dict:
    """One program (profile + 2 tags + 1 project w/ client) + one bare program + 1 orphan."""
    tax = TaxonomyDB(slug="service", name="Service", cardinality=Cardinality.MULTI)
    tax2 = TaxonomyDB(slug="geography", name="Geography", cardinality=Cardinality.MULTI)
    db.add_all([tax, tax2])
    await db.flush()
    tools = TaxonomyTermDB(taxonomy_id=tax.id, slug="tools", name="Tools")
    europe = TaxonomyTermDB(taxonomy_id=tax2.id, slug="europe", name="Europe")
    db.add_all([tools, europe])
    await db.flush()

    prog = ProgramDB(name="Alpha Program")
    bare = ProgramDB(name="Bare Program")
    db.add_all([prog, bare])
    await db.flush()
    db.add(PortfolioProfileDB(program_id=prog.id, stage="live", short_description="desc"))
    db.add(EntityTermDB(term_id=tools.id, taxonomy_id=tax.id, program_id=prog.id))
    db.add(EntityTermDB(term_id=europe.id, taxonomy_id=tax2.id, program_id=prog.id))

    acme = ClientDB(name="Acme", slug="acme")
    db.add(acme)
    await db.flush()
    member = ProjectDB(
        name="Alpha 2024",
        is_billable=True,
        is_absence=False,
        status="live",
        program_id=prog.id,
        client_id=acme.id,
        has_scorecard=True,
    )
    orphan = ProjectDB(name="Orphan", is_billable=True, is_absence=False, status="live")
    absence = ProjectDB(name="Holidays", is_billable=False, is_absence=True, status="live")
    db.add_all([member, orphan, absence])
    await db.commit()
    return {
        "prog": prog,
        "bare": bare,
        "tools": tools,
        "europe": europe,
        "acme": acme,
        "member": member,
        "orphan": orphan,
    }


@pytest.mark.asyncio
async def test_index_groups_programs_with_profile_terms_clients_projects(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    resp = await viewer.get("/api/portfolio/programs")
    assert resp.status_code == 200
    body = resp.json()
    alpha = next(p for p in body["programs"] if p["name"] == "Alpha Program")
    assert alpha["profile"]["stage"] == "live"
    assert {t["name"] for t in alpha["terms"]} == {"Tools", "Europe"}
    assert alpha["clients"] == [{"id": str(seed["acme"].id), "name": "Acme"}]
    assert alpha["projects"][0]["name"] == "Alpha 2024"
    assert alpha["projects"][0]["has_scorecard"] is True
    bare = next(p for p in body["programs"] if p["name"] == "Bare Program")
    assert bare["profile"] is None
    assert bare["terms"] == [] and bare["projects"] == []


@pytest.mark.asyncio
async def test_index_unassigned_tray_excludes_absence_and_ignores_filters(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_catalogue(db_session)
    resp = await viewer.get("/api/portfolio/programs", params={"search": "zzz-no-match"})
    body = resp.json()
    assert body["programs"] == []  # filter emptied the programs
    names = [p["name"] for p in body["unassigned_projects"]]
    assert names == ["Orphan"]  # tray unfiltered, absence project excluded


@pytest.mark.asyncio
async def test_index_term_filter_or_within_and_across_taxonomies(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    # Term from one taxonomy → Alpha matches, Bare doesn't.
    resp = await viewer.get("/api/portfolio/programs", params=[("term_ids", str(seed["tools"].id))])
    assert [p["name"] for p in resp.json()["programs"]] == ["Alpha Program"]
    # Terms from two taxonomies → AND across: Alpha has both → matches.
    resp = await viewer.get(
        "/api/portfolio/programs",
        params=[("term_ids", str(seed["tools"].id)), ("term_ids", str(seed["europe"].id))],
    )
    assert [p["name"] for p in resp.json()["programs"]] == ["Alpha Program"]


@pytest.mark.asyncio
async def test_index_client_filter(viewer: AsyncClient, db_session: AsyncSession) -> None:
    seed = await _seed_catalogue(db_session)
    resp = await viewer.get("/api/portfolio/programs", params={"client_id": str(seed["acme"].id)})
    assert [p["name"] for p in resp.json()["programs"]] == ["Alpha Program"]


@pytest.mark.asyncio
async def test_detail_returns_full_program(viewer: AsyncClient, db_session: AsyncSession) -> None:
    seed = await _seed_catalogue(db_session)
    resp = await viewer.get(f"/api/portfolio/programs/{seed['prog'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Alpha Program"
    assert body["profile"]["short_description"] == "desc"
    assert len(body["terms"]) == 2
    assert body["projects"][0]["client_name"] == "Acme"


@pytest.mark.asyncio
async def test_detail_404_for_unknown_program(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await viewer.get("/api/portfolio/programs/00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 404
