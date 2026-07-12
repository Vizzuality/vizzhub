"""Integration tests for /api/portfolio/programs (F2 catalogue)."""

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.models.client import ClientDB
from app.core.models.portfolio_profile import PortfolioProfileDB
from app.core.models.program import ProgramDB
from app.core.models.project import ProjectDB
from app.core.models.taxonomy import Cardinality, EntityTermDB, TaxonomyDB, TaxonomyTermDB
from app.core.models.user import UserDB
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
    # Ensure the test user exists so assigned_by FK is satisfied
    existing = (
        await db.execute(select(UserDB).where(UserDB.id == UUID(USER_ID)))
    ).scalar_one_or_none()
    if existing is None:
        db.add(UserDB(id=UUID(USER_ID), email="t@test.com"))
        await db.flush()

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
    db.add(
        PortfolioProfileDB(
            program_id=prog.id,
            stage="live",
            short_description="desc",
            objective="Restoring mangrove ecosystems in coastal areas",
        )
    )
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
    assert "unassigned_projects" not in body  # moved to Task 3's endpoint


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
    # OR within a taxonomy: Alpha has Tools but NOT Strategic — asking for either still matches.
    strategic = TaxonomyTermDB(
        taxonomy_id=seed["tools"].taxonomy_id, slug="strategic", name="Strategic"
    )
    db_session.add(strategic)
    await db_session.commit()
    resp = await viewer.get(
        "/api/portfolio/programs",
        params=[("term_ids", str(seed["tools"].id)), ("term_ids", str(strategic.id))],
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


@pytest.mark.asyncio
async def test_profile_patch_creates_row_when_absent(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    resp = await manager.patch(
        f"/api/portfolio/programs/{seed['bare'].id}/profile",
        json={"objective": "new obj", "on_website": True, "website_url": "https://example.org"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["objective"] == "new obj"
    assert body["on_website"] is True
    assert body["website_url"] == "https://example.org"
    row = (
        await db_session.execute(
            select(PortfolioProfileDB).where(PortfolioProfileDB.program_id == seed["bare"].id)
        )
    ).scalar_one()
    assert row.project_id is None


@pytest.mark.asyncio
async def test_profile_patch_rejects_non_http_website_url(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    resp = await manager.patch(
        f"/api/portfolio/programs/{seed['prog'].id}/profile",
        json={"website_url": "javascript:alert(1)"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_profile_patch_partial_update_preserves_unsent_fields(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    resp = await manager.patch(
        f"/api/portfolio/programs/{seed['prog'].id}/profile", json={"stage": "closing"}
    )
    assert resp.status_code == 200
    assert resp.json()["stage"] == "closing"
    assert resp.json()["short_description"] == "desc"  # untouched


@pytest.mark.asyncio
async def test_profile_patch_403_without_manage(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    resp = await viewer.patch(
        f"/api/portfolio/programs/{seed['prog'].id}/profile", json={"stage": "x"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_profile_patch_404_unknown_program(manager: AsyncClient) -> None:
    resp = await manager.patch(
        "/api/portfolio/programs/00000000-0000-0000-0000-000000000001/profile",
        json={"stage": "x"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_terms_put_replaces_taxonomy_set(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    strategic = TaxonomyTermDB(
        taxonomy_id=seed["tools"].taxonomy_id, slug="strategic", name="Strategic"
    )
    db_session.add(strategic)
    await db_session.commit()
    resp = await manager.put(
        f"/api/portfolio/programs/{seed['prog'].id}/terms",
        json={
            "taxonomy_id": str(seed["tools"].taxonomy_id),
            "term_ids": [str(strategic.id)],
            "primary_term_id": None,
        },
    )
    assert resp.status_code == 200
    assert [c["name"] for c in resp.json()] == ["Strategic"]
    rows = (
        (
            await db_session.execute(
                select(EntityTermDB).where(
                    EntityTermDB.program_id == seed["prog"].id,
                    EntityTermDB.taxonomy_id == seed["tools"].taxonomy_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1  # Tools replaced, not appended
    assert rows[0].assigned_by is not None


@pytest.mark.asyncio
async def test_terms_put_single_cardinality_rejects_two_terms(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    single = TaxonomyDB(slug="client-type", name="Client Type", cardinality=Cardinality.SINGLE)
    db_session.add(single)
    await db_session.flush()
    ngo = TaxonomyTermDB(taxonomy_id=single.id, slug="ngo", name="NGO")
    gov = TaxonomyTermDB(taxonomy_id=single.id, slug="government", name="Government")
    db_session.add_all([ngo, gov])
    await db_session.commit()
    resp = await manager.put(
        f"/api/portfolio/programs/{seed['prog'].id}/terms",
        json={
            "taxonomy_id": str(single.id),
            "term_ids": [str(ngo.id), str(gov.id)],
            "primary_term_id": None,
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_terms_put_primary_requires_allows_primary_and_membership(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    # service taxonomy has allows_primary=False (default)
    resp = await manager.put(
        f"/api/portfolio/programs/{seed['prog'].id}/terms",
        json={
            "taxonomy_id": str(seed["tools"].taxonomy_id),
            "term_ids": [str(seed["tools"].id)],
            "primary_term_id": str(seed["tools"].id),
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_terms_put_rejects_term_from_other_taxonomy(
    manager: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    resp = await manager.put(
        f"/api/portfolio/programs/{seed['prog'].id}/terms",
        json={
            "taxonomy_id": str(seed["tools"].taxonomy_id),
            "term_ids": [str(seed["europe"].id)],  # geography term
            "primary_term_id": None,
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_terms_put_403_without_manage(viewer: AsyncClient, db_session: AsyncSession) -> None:
    seed = await _seed_catalogue(db_session)
    resp = await viewer.put(
        f"/api/portfolio/programs/{seed['prog'].id}/terms",
        json={
            "taxonomy_id": str(seed["tools"].taxonomy_id),
            "term_ids": [],
            "primary_term_id": None,
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_index_is_paginated(viewer: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_catalogue(db_session)
    resp = await viewer.get("/api/portfolio/programs", params={"n": 1, "page": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["pages"] == 2
    assert len(body["programs"]) == 1
    assert body["programs"][0]["name"] == "Alpha Program"  # name order

    page2 = (await viewer.get("/api/portfolio/programs", params={"n": 1, "page": 2})).json()
    assert page2["programs"][0]["name"] == "Bare Program"


@pytest.mark.asyncio
async def test_search_matches_narrative_with_stemming(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_catalogue(db_session)
    # "restoration mangroves" stems to match "Restoring mangrove" in the objective
    resp = await viewer.get("/api/portfolio/programs", params={"search": "restoration mangroves"})
    body = resp.json()
    assert body["total"] == 1
    assert body["programs"][0]["name"] == "Alpha Program"


@pytest.mark.asyncio
async def test_search_name_match_outranks_narrative_match(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    seed = await _seed_catalogue(db_session)
    # Third program whose NAME contains the needle; Alpha only matches via narrative.
    named = ProgramDB(name="Mangrove Atlas")
    db_session.add(named)
    await db_session.commit()
    resp = await viewer.get("/api/portfolio/programs", params={"search": "mangrove"})
    names = [p["name"] for p in resp.json()["programs"]]
    assert names[0] == "Mangrove Atlas"
    assert "Alpha Program" in names


@pytest.mark.asyncio
async def test_search_shorter_than_two_chars_is_ignored(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_catalogue(db_session)
    resp = await viewer.get("/api/portfolio/programs", params={"search": "a"})
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_stage_filter(viewer: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_catalogue(db_session)
    piped = ProgramDB(name="Piped Program")
    db_session.add(piped)
    await db_session.flush()
    db_session.add(PortfolioProfileDB(program_id=piped.id, stage="pipeline"))
    await db_session.commit()
    resp = await viewer.get("/api/portfolio/programs", params={"stage": "pipeline"})
    body = resp.json()
    assert body["total"] == 1
    assert body["programs"][0]["name"] == "Piped Program"


@pytest.mark.asyncio
async def test_n_over_100_rejected(viewer: AsyncClient, db_session: AsyncSession) -> None:
    await _seed_catalogue(db_session)
    resp = await viewer.get("/api/portfolio/programs", params={"n": 500})
    assert resp.status_code == 400  # FastAPI validation mapped to 400 by global handler


@pytest.mark.asyncio
async def test_unassigned_endpoint_lists_orphans_not_absences(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_catalogue(db_session)
    resp = await viewer.get("/api/portfolio/programs/unassigned")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert names == ["Orphan"]  # absence project excluded, members excluded


@pytest.mark.asyncio
async def test_stages_endpoint_distinct_sorted_non_null(
    viewer: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_catalogue(db_session)
    piped = ProgramDB(name="Piped Program")
    piped2 = ProgramDB(name="Piped Two")
    db_session.add_all([piped, piped2])
    await db_session.flush()
    db_session.add(PortfolioProfileDB(program_id=piped.id, stage="pipeline"))
    db_session.add(PortfolioProfileDB(program_id=piped2.id, stage="pipeline"))
    await db_session.commit()
    resp = await viewer.get("/api/portfolio/programs/stages")
    assert resp.status_code == 200
    assert resp.json() == ["live", "pipeline"]  # distinct (pipeline ×2 → once), sorted
